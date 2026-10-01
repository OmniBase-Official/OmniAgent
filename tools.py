"""Tool implementations exposed to the OmniAgent ReAct loop.

Each tool declares its arguments as a pydantic model and receives a validated
instance of it. The raw ``Action Input`` line the model emitted is turned into
that model by :func:`parse_tool_args`, which accepts the shapes small models
actually produce -- a bare value, a JSON object, or nothing.

Dispatch never raises: bad arguments and crashing tools both come back as an
``Error: ...`` string, which the agent reads as an Observation and can recover
from.
"""

from __future__ import annotations

import ast
import logging
import math
import operator
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

import observability as obs

_log = obs.get_logger("tools")

# --------------------------------------------------------------------------- #
# calculate
# --------------------------------------------------------------------------- #

_BIN_OPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type, Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_CONSTANTS: dict[str, float] = {"pi": math.pi, "e": math.e, "tau": math.tau}

_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "log": math.log,
    "log2": math.log2,
    "log10": math.log10,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "degrees": math.degrees,
    "radians": math.radians,
    "floor": math.floor,
    "ceil": math.ceil,
    "factorial": math.factorial,
}

# Guards against expressions that are cheap to type but expensive to evaluate,
# e.g. 9**9**9 or factorial(10**6).
_MAX_EXPONENT = 1_000
_MAX_FACTORIAL = 1_000
_MAX_EXPRESSION_LEN = 500


class CalculationError(ValueError):
    """Raised when an expression is unsupported or cannot be evaluated."""


def _eval_node(node: ast.AST) -> float:  # noqa: PLR0912 - one branch per allowed node type
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise CalculationError(f"unsupported literal: {node.value!r}")
        return node.value

    if isinstance(node, ast.BinOp):
        binary_op = _BIN_OPS.get(type(node.op))
        if binary_op is None:
            raise CalculationError(f"unsupported operator: {type(node.op).__name__}")
        left, right = _eval_node(node.left), _eval_node(node.right)
        if binary_op is operator.pow and abs(right) > _MAX_EXPONENT:
            raise CalculationError(f"exponent too large (max {_MAX_EXPONENT})")
        return binary_op(left, right)

    if isinstance(node, ast.UnaryOp):
        unary_op = _UNARY_OPS.get(type(node.op))
        if unary_op is None:
            raise CalculationError(f"unsupported unary operator: {type(node.op).__name__}")
        return unary_op(_eval_node(node.operand))

    if isinstance(node, ast.Name):
        if node.id not in _CONSTANTS:
            raise CalculationError(f"unknown name: {node.id!r}")
        return _CONSTANTS[node.id]

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise CalculationError("only direct calls to allowed functions are supported")
        name = node.func.id
        func = _FUNCTIONS.get(name)
        if func is None:
            raise CalculationError(f"unknown function: {name!r}")
        if node.keywords:
            raise CalculationError("keyword arguments are not supported")
        args = [_eval_node(arg) for arg in node.args]
        if name == "factorial" and (len(args) != 1 or args[0] > _MAX_FACTORIAL):
            raise CalculationError(f"factorial argument too large (max {_MAX_FACTORIAL})")
        return func(*args)

    raise CalculationError(f"unsupported syntax: {type(node).__name__}")


def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression and return the result as text.

    The expression is parsed into an AST and walked with an explicit allow-list,
    so no arbitrary Python ever executes. Supports ``+ - * / // % **``,
    parentheses, the constants pi/e/tau and common math functions.
    """
    expression = (expression or "").strip().strip("`").strip()
    if expression.lower().startswith("expression="):
        expression = expression.split("=", 1)[1].strip().strip("\"'")

    if not expression:
        return "Error: empty expression. Provide something like '(12 * 7) + 5'."
    if len(expression) > _MAX_EXPRESSION_LEN:
        return f"Error: expression too long (max {_MAX_EXPRESSION_LEN} characters)."

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return (
            f"Error: could not parse {expression!r} as an arithmetic "
            f"expression ({exc.msg})."
        )

    try:
        result = _eval_node(tree)
    except CalculationError as exc:
        return f"Error: {exc}"
    except ZeroDivisionError:
        return "Error: division by zero."
    except (OverflowError, ValueError) as exc:
        return f"Error: {exc}"

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    elif isinstance(result, float):
        result = round(result, 10)
    return f"{expression} = {result}"



# --------------------------------------------------------------------------- #
# get_current_time
# --------------------------------------------------------------------------- #


def get_current_time() -> str:
    """Return the current local date and time, plus the UTC equivalent."""
    now = datetime.now().astimezone()
    utc = now.astimezone(timezone.utc)
    return (
        f"Local time: {now.strftime('%Y-%m-%d %H:%M:%S')} "
        f"({now.strftime('%A')}, UTC{now.strftime('%z')}) | "
        f"UTC: {utc.strftime('%Y-%m-%d %H:%M:%S')}"
    )


# --------------------------------------------------------------------------- #
# argument schemas
# --------------------------------------------------------------------------- #


class ToolArgs(BaseModel):
    """Base class for a tool's arguments.

    ``extra="forbid"`` matters here: when a model invents a field name we want a
    validation error it can read and correct, not a silently ignored value.
    """

    model_config = ConfigDict(extra="forbid")


class CalculateArgs(ToolArgs):
    expression: str = Field(
        min_length=1,
        max_length=_MAX_EXPRESSION_LEN,
        description=(
            "The arithmetic expression to evaluate, e.g. '(1250 * 0.07) + sqrt(144)'."
        ),
    )


class NoArgs(ToolArgs):
    """For tools that take nothing at all."""


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #

ArgsT = TypeVar("ArgsT", bound=ToolArgs)


def _type_name(annotation: object) -> str:
    return str(getattr(annotation, "__name__", annotation))


@dataclass(frozen=True)
class Tool(Generic[ArgsT]):
    """A single callable exposed to the agent.

    Arguments are described by a pydantic model rather than parsed by each tool,
    so validation, the error message a model sees, and the signature printed
    into the system prompt all come from one declaration.
    """

    name: str
    description: str
    args_model: type[ArgsT]
    run: Callable[[ArgsT], str]
    example: str

    @property
    def signature(self) -> str:
        """``name(field: type, ...)``, derived from the schema."""
        params = ", ".join(
            f"{field_name}: {_type_name(field.annotation)}"
            for field_name, field in self.args_model.model_fields.items()
        )
        return f"{self.name}({params})"


def _run_calculate(args: CalculateArgs) -> str:
    return calculate(args.expression)


def _run_get_current_time(_args: NoArgs) -> str:
    return get_current_time()


TOOLS: dict[str, Tool[Any]] = {
    "calculate": Tool(
        name="calculate",
        description=(
            "Evaluate a mathematical expression. Use it for ANY arithmetic instead "
            "of doing the maths yourself. Supports + - * / // % ** ( ), the "
            "constants pi/e/tau and functions such as sqrt, log, log10, exp, sin, "
            "cos, tan, floor, ceil, round, abs, min, max, factorial."
        ),
        args_model=CalculateArgs,
        run=_run_calculate,
        example="(1250 * 0.07) + sqrt(144)",
    ),
    "get_current_time": Tool(
        name="get_current_time",
        description=(
            "Return the current local date and time (and the UTC equivalent). "
            "Takes no arguments. Use it whenever the user asks about 'now', "
            "'today', the date, the day of the week, or the current time."
        ),
        args_model=NoArgs,
        run=_run_get_current_time,
        example="none",
    ),
}


class ToolArgumentError(ValueError):
    """Raised when an Action Input cannot be turned into a tool's arguments."""


# --------------------------------------------------------------------------- #
# prompt rendering
# --------------------------------------------------------------------------- #


def _describe_fields(tool: Tool[Any]) -> str:
    lines = []
    for field_name, field in tool.args_model.model_fields.items():
        required = "required" if field.is_required() else "optional"
        lines.append(
            f"    {field_name} ({_type_name(field.annotation)}, {required}): "
            f"{field.description or ''}".rstrip()
        )
    return "\n".join(lines)


def describe_tools() -> str:
    """Render the tool catalogue for injection into the system prompt.

    Generated from the schemas, so the prompt cannot drift away from the code.
    """
    blocks = []
    for tool in TOOLS.values():
        block = f"- {tool.signature}\n  {tool.description}"
        fields = _describe_fields(tool)
        if fields:
            block += f"\n  Arguments:\n{fields}"
        block += f"\n  Example -> Action: {tool.name}\n             Action Input: {tool.example}"
        blocks.append(block)
    return "\n".join(blocks)


def tool_names() -> str:
    return ", ".join(TOOLS)


# --------------------------------------------------------------------------- #
# argument parsing + dispatch
# --------------------------------------------------------------------------- #


def _input_hint(tool: Tool[Any]) -> str:
    """How this tool's Action Input should look, in one phrase."""
    fields = tool.args_model.model_fields
    if not fields:
        return "'none', since this tool takes no arguments."
    if len(fields) == 1:
        only_field = next(iter(fields))
        return f"the {only_field} itself on one line, e.g. '{tool.example}'."
    names = ", ".join(f'"{name}": ...' for name in fields)
    return "a JSON object, e.g. {" + names + "}."


def _format_validation_error(tool: Tool[Any], error: ValidationError) -> str:
    """Turn a pydantic error into something a 7B model can act on."""
    problems = [
        f"{'.'.join(str(part) for part in item['loc']) or 'input'}: {item['msg']}"
        for item in error.errors()
    ]
    return (
        f"invalid arguments for {tool.signature} -- "
        + "; ".join(problems)
        + f". Action Input should be {_input_hint(tool)}"
    )


def parse_tool_args(tool: Tool[ArgsT], raw_input: str) -> ArgsT:
    """Turn a raw ``Action Input`` line into a validated arguments model.

    Three shapes are accepted, because small models reach for all of them:

    * a JSON object -- ``{"expression": "2 + 2"}``
    * the bare value, for a tool with exactly one field -- ``2 + 2``
    * nothing at all, for a tool with no fields
    """
    value = raw_input.strip()
    fields = tool.args_model.model_fields

    try:
        if value.startswith("{"):
            return tool.args_model.model_validate_json(value)
        if not fields:
            return tool.args_model()
        if len(fields) == 1:
            return tool.args_model.model_validate({next(iter(fields)): value})
    except ValidationError as exc:
        raise ToolArgumentError(_format_validation_error(tool, exc)) from exc

    raise ToolArgumentError(
        f"invalid arguments for {tool.signature} -- Action Input should be {_input_hint(tool)}"
    )


def run_tool(name: str, tool_input: str) -> str:
    """Dispatch to a tool by name, returning its Observation text."""
    tool = TOOLS.get(name.strip())
    if tool is None:
        obs.event(
            "tool.unknown",
            logger=_log,
            level=logging.WARNING,
            requested=name,
            available=list(TOOLS),
        )
        return f"Error: unknown tool {name!r}. Available tools are: {tool_names()}."

    try:
        args = parse_tool_args(tool, tool_input)
    except ToolArgumentError as exc:
        obs.event(
            "tool.invalid_args",
            logger=_log,
            level=logging.WARNING,
            tool=tool.name,
            tool_input=tool_input,
            reason=str(exc),
        )
        return f"Error: {exc}"

    try:
        return tool.run(args)
    except Exception as exc:  # noqa: BLE001 - a tool must never crash the loop
        obs.event(
            "tool.crashed",
            logger=_log,
            level=logging.ERROR,
            tool=tool.name,
            tool_input=tool_input,
            exc_info=True,
        )
        return f"Error: tool {name!r} raised {type(exc).__name__}: {exc}"
