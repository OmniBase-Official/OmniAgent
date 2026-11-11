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
import tomllib
from collections.abc import Callable, Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

import observability as obs
from config_inspection import inspect_config_precedence as _inspect_config_precedence
from sandbox import (
    _BINARY_SNIFF_BYTES,
    MAX_READ_CHARS,
    TRUNCATION_NOTE,
    SandboxError,
    Workspace,
    get_workspace,
)

_log = obs.get_logger("tools")

#: The stable part of the sandbox's truncation note, used to spot a capped read.
_TRUNCATION_PREFIX = TRUNCATION_NOTE.split("{", 1)[0].rstrip()
_PAIR_SIZE = 2

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
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
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
    utc = now.astimezone(UTC)
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

def _type_name(annotation: object) -> str:
    return str(getattr(annotation, "__name__", annotation))


@dataclass(frozen=True)
class Tool[ArgsT: ToolArgs]:
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
    bare_field: str | None = None

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
            "Evaluate arithmetic with + - * / // % **, constants pi/e/tau, and "
            "allowed math functions. Use for every calculation; arbitrary code is refused."
        ),
        args_model=CalculateArgs,
        run=_run_calculate,
        example="(1250 * 0.07) + sqrt(144)",
    ),
    "get_current_time": Tool(
        name="get_current_time",
        description=(
            "Return local and UTC date/time. Use for current date, day, or time questions."
        ),
        args_model=NoArgs,
        run=_run_get_current_time,
        example="none",
    ),
}

# Runtime capabilities are closed even if another module mutates the registry.
# Task-level allowlists may narrow this set, but can never widen it.
FIXED_TOOL_ALLOWLIST = frozenset(
    {
        "calculate",
        "get_current_time",
        "read_file",
        "list_directory",
        "search_text",
        "file_info",
        "inspect_config_precedence",
    }
)

# This bounded static inspection is an internal capability, not a tool.
FIXED_INTERNAL_CAPABILITY_ALLOWLIST = frozenset({"inspect_default_model_cli"})


class ToolArgumentError(ValueError):
    """Raised when an Action Input cannot be turned into a tool's arguments."""


#: What a model writes when it means "this tool takes nothing". Canonical here
#: rather than in the agent, so run_tool() is correct when called on its own.
NO_ARG_INPUTS = frozenset(
    {"", "none", "null", "n/a", "na", "-", "nothing", "()", "no input"}
)


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
        if tool.example:
            block += (
                f"\n  Example -> Action: {tool.name}"
                f"\n             Action Input: {tool.example}"
            )
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


def parse_tool_args[ArgsT: ToolArgs](tool: Tool[ArgsT], raw_input: str) -> ArgsT:
    """Turn a raw ``Action Input`` line into a validated arguments model.

    Three shapes are accepted, because small models reach for all of them:

    * a JSON object -- ``{"expression": "2 + 2"}``
    * the bare value, for a tool with exactly one field -- ``2 + 2``
    * nothing at all, for a tool with no fields
    """
    value = raw_input.strip()
    fields = tool.args_model.model_fields
    if value.lower() in NO_ARG_INPUTS:
        value = ""

    try:
        if value.startswith("{"):
            return tool.args_model.model_validate_json(value)
        if not fields:
            return tool.args_model()
        # No input and nothing required: the model meant "use the defaults".
        if not value and not any(field.is_required() for field in fields.values()):
            return tool.args_model()
        required_fields = [name for name, field in fields.items() if field.is_required()]
        if tool.bare_field is not None:
            return tool.args_model.model_validate({tool.bare_field: value})
        if len(required_fields) == 1 and len(fields) == 1:
            return tool.args_model.model_validate({required_fields[0]: value})
        if len(fields) == 1:
            return tool.args_model.model_validate({next(iter(fields)): value})
    except ValidationError as exc:
        raise ToolArgumentError(_format_validation_error(tool, exc)) from exc

    raise ToolArgumentError(
        f"invalid arguments for {tool.signature} -- Action Input should be {_input_hint(tool)}"
    )


def run_tool(
    name: str,
    tool_input: str,
    *,
    allowed_tools: Collection[str] | None = None,
) -> str:
    """Dispatch to a tool by name, returning its Observation text."""
    normalized_name = name.strip()
    if normalized_name not in FIXED_TOOL_ALLOWLIST:
        obs.event(
            "tool.unknown",
            logger=_log,
            level=logging.WARNING,
            status="rejected",
        )
        available = ", ".join(name for name in TOOLS if name in FIXED_TOOL_ALLOWLIST)
        return (
            f"Error: there is no tool called {name!r}, and naming one does not create "
            f"the capability. If no available tool can get the information, then you "
            f"cannot find it out, and saying so is the answer. Available tools are: "
            f"{available}."
        )

    task_allowlist = FIXED_TOOL_ALLOWLIST if allowed_tools is None else allowed_tools
    if normalized_name not in task_allowlist:
        obs.event(
            "tool.unknown",
            logger=_log,
            level=logging.WARNING,
            status="rejected",
        )
        return "Error: tool is not allowed for this task."

    tool = TOOLS.get(normalized_name)
    if tool is None:
        obs.event(
            "tool.unknown",
            logger=_log,
            level=logging.WARNING,
            status="rejected",
        )
        # Saying only "unknown tool" was not enough. Asked for the weather in
        # Bangkok with seven earlier questions in history, the agent invented
        # get_current_weather, read that error, and reported 35 degrees and 89%
        # humidity -- in all three recorded runs, while the same question with
        # a fresh agent was answered honestly in all three. So the error states
        # the consequence: a tool that does not exist means the information is
        # not available, not that it should come from somewhere else.
        return (
            f"Error: there is no tool called {name!r}, and naming one does not create "
            f"the capability. If nothing in this list can get the information, then you "
            f"cannot find it out, and saying so is the answer -- do not supply the value "
            f"yourself. Available tools are: {tool_names()}."
        )

    try:
        args = parse_tool_args(tool, tool_input)
    except ToolArgumentError as exc:
        obs.event(
            "tool.invalid_args",
            logger=_log,
            level=logging.WARNING,
            status="rejected",
            tool_name=tool.name,
        )
        return f"Error: {exc}"

    try:
        return tool.run(args)
    except Exception as exc:  # noqa: BLE001 - a tool must never crash the loop
        obs.event(
            "tool.crashed",
            logger=_log,
            level=logging.ERROR,
            status="error",
            tool_name=tool.name,
        )
        return f"Error: tool {name!r} raised {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# file tools
# --------------------------------------------------------------------------- #
# Every path these take is chosen by the model, and everything they return ends
# up in the log and then in the training dataset. The containment rules live in
# sandbox.py; these functions only shape the output.

#: Most matches search_text will report before it stops looking.
#: What read_file will hand back in full. Past this it refuses outright rather
#: than returning the start of the file. An excerpt cannot be told apart from
#: the whole, and three separate fabrications came out of capped reads on the
#: 1.5B: a line count copied from the previous turn, "the word 'budget' is not
#: used anywhere in the file" about a file that uses it, and a quotation that
#: was not in the file at all. A refusal can only be read one way.
#:
#: Sized to the agent's per-observation budget, which this module cannot import
#: because the agent imports this one. A test holds the two together instead:
#: read_file must never return something cap_observation would trim.
MAX_INTACT_READ_CHARS = 2_400

MAX_SEARCH_MATCHES = 50

#: Most files search_text will open in one call.
MAX_SEARCH_FILES = 400


def read_file(
    path: str, start_line: int | None = None, end_line: int | None = None
) -> str:
    """Return a file's contents, numbered by line, from inside the workspace."""
    workspace = get_workspace()
    if (start_line is None) != (end_line is None):
        return "Error: provide both start_line and end_line for a ranged read."
    if start_line is not None and end_line is not None:
        try:
            ranged_text = workspace.read_text_range(path, start_line, end_line)
        except SandboxError as exc:
            return f"Error: {exc}"
        except OSError as exc:
            return f"Error: could not read {path!r}: {exc.strerror or exc}"
        if len(ranged_text) > MAX_INTACT_READ_CHARS:
            return (
                f"Error: requested lines from {path!r} exceed the "
                f"{MAX_INTACT_READ_CHARS}-character tool limit; request a narrower range."
            )
        return ranged_text

    try:
        text = workspace.read_text(path)
    except SandboxError as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: could not read {path!r}: {exc.strerror or exc}"

    resolved = workspace.resolve(path)
    shown = workspace.display(resolved)
    if not text.strip():
        return f"{shown} is empty."

    lines = text.splitlines()
    numbered = "\n".join(f"{number:>5}  {line}" for number, line in enumerate(lines, start=1))
    size = resolved.stat().st_size

    # State the line count rather than leaving the model to work it out. Asked
    # how many lines a 278-line file had, a 1.5B model read the whole thing and
    # answered 10,306 -- the number was in the output and it still guessed.
    # Facts the tool already knows should not be left to the model.
    rendered = f"{shown} ({len(lines):,} lines, {size:,} bytes):\n{numbered}"
    if len(rendered) <= MAX_INTACT_READ_CHARS:
        return rendered

    size_phrase = (
        f"over {MAX_READ_CHARS:,} characters"
        if _TRUNCATION_PREFIX in text
        else f"{len(text):,} characters"
    )
    return (
        f"Error: {shown} is {size_phrase}, too long to return in full. Reading the "
        f"start of it would not tell you what the rest contains. For a relevant section, "
        f"use read_file with JSON like {{\"path\":\"file.py\",\"start_line\":1,"
        f"\"end_line\":20}}. Use file_info for size or line facts and search_text "
        f"to locate relevant text."
    )


def list_directory(path: str = ".") -> str:
    """Return the visible entries of a directory inside the workspace."""
    workspace = get_workspace()
    try:
        entries = workspace.list_dir(path)
        shown = workspace.display(workspace.resolve(path or "."))
    except SandboxError as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: could not list {path!r}: {exc.strerror or exc}"

    if not entries:
        return f"{shown} is empty."
    return f"{shown}:\n" + "\n".join(f"  {entry}" for entry in entries)


def search_text(  # noqa: PLR0912 - a guard per thing that can go wrong in a walk
    query: str, path: str = "."
) -> str:
    """Find a literal substring in the files under a path.

    Literal, not regex, on purpose: a model-supplied regex is a denial-of-
    service waiting to happen, and Python's engine has no timeout.
    """
    workspace = get_workspace()
    needle = query.strip()
    if not needle:
        return "Error: no search text given."

    try:
        start = workspace.resolve(path or ".")
    except SandboxError as exc:
        return f"Error: {exc}"

    candidates = [start] if start.is_file() else sorted(start.rglob("*"))
    matches: list[str] = []
    scanned = 0
    lowered = needle.lower()

    for candidate in candidates:
        if len(matches) >= MAX_SEARCH_MATCHES or scanned >= MAX_SEARCH_FILES:
            break
        if not candidate.is_file():
            continue
        try:
            resolved = workspace.resolve(workspace.display(candidate))
        except SandboxError:
            continue  # hidden, denied, or escaping: skip quietly
        if resolved.stat().st_size > workspace.max_file_bytes:
            continue

        scanned += 1
        try:
            blob = resolved.read_bytes()
        except OSError:
            continue
        if b"\0" in blob[:_BINARY_SNIFF_BYTES]:
            continue

        shown = workspace.display(resolved)
        for number, line in enumerate(
            blob.decode("utf-8", errors="replace").splitlines(), start=1
        ):
            if lowered in line.lower():
                matches.append(f"{shown}:{number}: {line.strip()[:200]}")
                if len(matches) >= MAX_SEARCH_MATCHES:
                    break

    if not matches and scanned == 0:
        return (
            f"No match for {needle!r} in {workspace.display(start)} (0 files searched). "
            "No readable files were found under this path. Check it with list_directory "
            "or search from the workspace root '.'; do not assume a source subdirectory."
        )
    if not matches:
        return f"No match for {needle!r} in {workspace.display(start)} ({scanned} files searched)."
    header = f"{len(matches)} match{'es' if len(matches) != 1 else ''} for {needle!r}"
    if len(matches) >= MAX_SEARCH_MATCHES:
        header += " (stopped at the limit)"
    return f"{header}:\n" + "\n".join(matches)


class ReadFileArgs(ToolArgs):
    path: str = Field(
        min_length=1,
        max_length=1_000,
        description="Path relative to the workspace root, e.g. 'README.md' or 'src/app.py'.",
    )
    start_line: int | None = Field(
        default=None,
        ge=1,
        description="First line to return for a bounded read; provide it with end_line.",
    )
    end_line: int | None = Field(
        default=None,
        ge=1,
        description="Last line to return for a bounded read; maximum range is 100 lines.",
    )


class ListDirectoryArgs(ToolArgs):
    path: str = Field(
        default=".",
        max_length=1_000,
        description="Directory relative to the workspace root. Defaults to the root itself.",
    )


class SearchTextArgs(ToolArgs):
    query: str = Field(
        min_length=1,
        max_length=200,
        description="Literal text to look for. Not a regular expression.",
    )
    path: str = Field(
        default=".",
        max_length=1_000,
        description="Directory or file to search under. Defaults to the workspace root.",
    )


def _run_read_file(args: ReadFileArgs) -> str:
    return read_file(args.path, args.start_line, args.end_line)


def _run_list_directory(args: ListDirectoryArgs) -> str:
    return list_directory(args.path)


def _run_search_text(args: SearchTextArgs) -> str:
    return search_text(args.query, args.path)


def _named_assignment(
    statement: ast.stmt, name: str
) -> tuple[ast.expr, ast.expr] | None:
    if (
        isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and statement.targets[0].id == name
    ):
        return statement.targets[0], statement.value
    if (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == name
        and statement.value is not None
    ):
        return statement.target, statement.value
    return None


def inspect_config_precedence(path: str) -> str:
    """Preserve the public tool facade for static config precedence inspection."""
    return _inspect_config_precedence(path)


def _read_static_source(workspace: Workspace, path: str) -> tuple[str, str]:
    admitted = workspace.resolve(path)
    display = workspace.display(admitted)
    source = workspace.read_text(display)
    marker = TRUNCATION_NOTE.format(limit=workspace.max_read_chars)
    if marker in source:
        raise ValueError(f"{display} is too large to inspect completely")
    return source, display


def _builtin_model(workspace: Workspace) -> tuple[str, int]:
    agent_path = workspace.display(workspace.resolve("agent.py"))
    result = search_text('DEFAULT_MODEL = "', agent_path)
    if result.startswith(("Error:", "No match")):
        raise ValueError("could not locate DEFAULT_MODEL in agent.py")
    matches = []
    for line in result.splitlines()[1:]:
        _, _, match = line.partition(":")
        line_text, separator, source_line = match.partition(":")
        if separator and line_text.isdigit() and source_line.startswith(" DEFAULT_MODEL ="):
            matches.append((int(line_text), source_line.strip()))
    if len(matches) != 1:
        raise ValueError("expected one DEFAULT_MODEL declaration in agent.py")
    line_number, source_line = matches[0]
    statement = ast.parse(source_line).body
    if len(statement) != 1 or not isinstance(statement[0], ast.Assign):
        raise ValueError("DEFAULT_MODEL must be a simple module assignment")
    pair = _named_assignment(statement[0], "DEFAULT_MODEL")
    if pair is None or not isinstance(pair[1], ast.Constant) or not isinstance(pair[1].value, str):
        raise ValueError("DEFAULT_MODEL must be a static string")
    return pair[1].value, line_number


def _configured_model(source: str) -> tuple[str, int]:
    data = tomllib.loads(source)
    defaults = data.get("defaults")
    if not isinstance(defaults, dict) or not isinstance(defaults.get("model"), str):
        raise TypeError("omniagent.toml must declare a string [defaults].model")
    in_defaults = False
    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("["):
            in_defaults = stripped == "[defaults]"
        elif in_defaults and "=" in stripped and stripped.partition("=")[0].strip() == "model":
            return defaults["model"], line_number
    raise ValueError("could not locate [defaults].model in omniagent.toml")


def _is_model_mapping(node: ast.AST) -> bool:
    if not isinstance(node, ast.DictComp) or not isinstance(node.key, ast.Name):
        return False
    target_name = node.key.id
    if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name):
        return False
    if node.value.func.id != "getattr" or len(node.value.args) != _PAIR_SIZE:
        return False
    first, second = node.value.args
    if not isinstance(first, ast.Name) or first.id != "args":
        return False
    if not isinstance(second, ast.Name) or second.id != node.key.id:
        return False
    if not any(
        isinstance(generator.iter, ast.Tuple)
        and any(
            isinstance(item, ast.Constant) and item.value == "model"
            for item in generator.iter.elts
        )
        and isinstance(generator.target, ast.Name)
        and generator.target.id == target_name
        for generator in node.generators
    ):
        return False
    if len(node.generators) != 1 or len(node.generators[0].ifs) != 1:
        return False
    guard = node.generators[0].ifs[0]
    return (
        isinstance(guard, ast.Compare)
        and isinstance(guard.left, ast.Call)
        and isinstance(guard.left.func, ast.Name)
        and guard.left.func.id == "getattr"
        and len(guard.left.args) == _PAIR_SIZE
        and isinstance(guard.left.args[0], ast.Name)
        and guard.left.args[0].id == first.id
        and isinstance(guard.left.args[1], ast.Name)
        and guard.left.args[1].id == target_name
        and len(guard.ops) == 1
        and isinstance(guard.ops[0], ast.IsNot)
        and len(guard.comparators) == 1
        and isinstance(guard.comparators[0], ast.Constant)
        and guard.comparators[0].value is None
    )


def _cli_model_lines(source: str) -> tuple[int, int, int]:
    module = ast.parse(source)
    named_functions = {
        name: [
            node for node in module.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        for name in ("parse_args", "cli_settings", "main")
    }
    if any(len(functions) != 1 for functions in named_functions.values()):
        raise ValueError("expected one top-level parse_args(), cli_settings(), and main()")
    parse_function = named_functions["parse_args"][0]
    cli_function = named_functions["cli_settings"][0]
    main_function = named_functions["main"][0]
    parser_creations = [
        statement
        for statement in parse_function.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr == "ArgumentParser"
        and isinstance(statement.value.func.value, ast.Name)
        and statement.value.func.value.id == "argparse"
    ]
    parser_binding = None
    if (
        len(parser_creations) == 1
        and isinstance(parser_creations[0].targets[0], ast.Name)
    ):
        parser_binding = parser_creations[0].targets[0].id
    parser_assignments = [
        node
        for node in ast.walk(parse_function)
        if isinstance(node, ast.Name)
        and node.id == parser_binding
        and isinstance(node.ctx, ast.Store)
    ] if parser_binding is not None else []
    parser_groups = [
        statement
        for statement in parse_function.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr == "add_argument_group"
        and isinstance(statement.value.func.value, ast.Name)
        and parser_binding is not None
        and statement.value.func.value.id == parser_binding
    ]
    group_binding = (
        parser_groups[0].targets[0].id
        if len(parser_groups) == 1 and isinstance(parser_groups[0].targets[0], ast.Name)
        else None
    )
    group_bindings = [
        node
        for node in ast.walk(parse_function)
        if isinstance(node, ast.Name)
        and node.id == group_binding
        and isinstance(node.ctx, ast.Store)
    ] if group_binding is not None else []
    flags = [
        statement.value
        for statement in parse_function.body
        if isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr == "add_argument"
        and isinstance(statement.value.func.value, ast.Name)
        and statement.value.func.value.id in {parser_binding, group_binding}
        and any(
            isinstance(arg, ast.Constant) and arg.value == "--model"
            for arg in statement.value.args
        )
    ]
    cli_parameters = [
        argument.arg for argument in cli_function.args.args
    ]
    comprehensions = [node for node in ast.walk(cli_function) if isinstance(node, ast.DictComp)]
    mappings = [node for node in comprehensions if _is_model_mapping(node)]
    model_mapping_assignments = [
        statement
        for statement in cli_function.body
        if isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.value in mappings
    ]
    model_mapping_returns = [
        statement
        for statement in cli_function.body
        if isinstance(statement, ast.Return)
        and isinstance(statement.value, ast.Name)
        and len(model_mapping_assignments) == 1
        and isinstance(model_mapping_assignments[0].target, ast.Name)
        and statement.value.id == model_mapping_assignments[0].target.id
    ]
    if (
        cli_parameters != ["args"]
        or len(comprehensions) != 1
        or len(model_mapping_assignments) != 1
        or len(model_mapping_returns) != 1
        or model_mapping_assignments[0].lineno >= model_mapping_returns[0].lineno
    ):
        mappings = []
    parse_results = [
        statement
        for statement in parse_function.body
        if isinstance(statement, ast.Assign)
        and len(statement.targets) == 1
        and isinstance(statement.targets[0], ast.Name)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr == "parse_args"
        and isinstance(statement.value.func.value, ast.Name)
        and parser_binding is not None
        and statement.value.func.value.id == parser_binding
        and len(statement.value.args) == 1
        and isinstance(statement.value.args[0], ast.Name)
        and len(parse_function.args.args) == 1
        and statement.value.args[0].id == parse_function.args.args[0].arg
    ]
    parsed_binding = (
        parse_results[0].targets[0].id
        if len(parse_results) == 1
        and isinstance(parse_results[0].targets[0], ast.Name)
        else None
    )
    parse_returns = [node for node in ast.walk(parse_function) if isinstance(node, ast.Return)]
    valid_parse_return = (
        len(parse_function.body) > 0
        and len(parse_returns) == 1
        and parse_function.body[-1] is parse_returns[0]
        and isinstance(parse_returns[0].value, ast.Name)
        and parsed_binding is not None
        and parse_returns[0].value.id == parsed_binding
    )
    main_parse = (
        main_function.body[0]
        if main_function.body and isinstance(main_function.body[0], ast.Assign)
        else None
    )
    live_binding = (
        main_parse.targets[0].id
        if isinstance(main_parse, ast.Assign)
        and len(main_parse.targets) == 1
        and isinstance(main_parse.targets[0], ast.Name)
        and isinstance(main_parse.value, ast.Call)
        and isinstance(main_parse.value.func, ast.Name)
        and main_parse.value.func.id == "parse_args"
        else None
    )
    resolve_calls = [
        node for node in ast.walk(main_function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve"
    ]
    resolve_assignment = next(
        (
            statement
            for statement in main_function.body
            if isinstance(statement, ast.Try)
            and statement.body
            and isinstance(statement.body[0], ast.Assign)
            and isinstance(statement.body[0].value, ast.Call)
            and isinstance(statement.body[0].value.func, ast.Name)
            and statement.body[0].value.func.id == "resolve"
        ),
        None,
    )
    live_resolve = (
        resolve_assignment.body[0].value
        if resolve_assignment is not None
        and isinstance(resolve_assignment.body[0], ast.Assign)
        and isinstance(resolve_assignment.body[0].value, ast.Call)
        else None
    )
    resolves = [
        node for node in resolve_calls
        if node is live_resolve
        and node.args
        and isinstance(node.args[0], ast.Call)
        and isinstance(node.args[0].func, ast.Name)
        and node.args[0].func.id == "cli_settings"
        and len(node.args[0].args) == 1
        and isinstance(node.args[0].args[0], ast.Name)
        and live_binding is not None
        and node.args[0].args[0].id == live_binding
    ]
    resolve_try_index = (
        main_function.body.index(resolve_assignment)
        if resolve_assignment is not None
        else 0
    )
    returns_before_resolution = (
        any(
            isinstance(node, ast.Return)
            for statement in main_function.body[1:resolve_try_index]
            for node in ast.walk(statement)
        )
        if resolve_assignment is not None
        else True
    )
    if (
        len(flags) != 1
        or len(mappings) != 1
        or len(resolves) != 1
        or len(parse_results) != 1
        or not valid_parse_return
        or parser_binding is None
        or len(parser_assignments) != 1
        or parser_assignments[0] is not parser_creations[0].targets[0]
        or not parser_creations
        or len(parser_groups) != 1
        or group_binding is None
        or len(group_bindings) != 1
        or group_bindings[0] is not parser_groups[0].targets[0]
        or parser_groups[0].lineno >= flags[0].lineno
        or parser_creations[0].lineno >= flags[0].lineno
        or flags[0].lineno >= parse_results[0].lineno
        or live_binding is None
        or resolve_assignment is None
        or not resolve_assignment.body
        or resolve_assignment.body[0].lineno <= main_function.body[0].lineno
        or returns_before_resolution
    ):
        raise ValueError("could not prove --model reaches resolve() through cli_settings()")
    return flags[0].lineno, mappings[0].lineno, resolves[0].lineno


def inspect_default_model_cli() -> str:
    """Read static default-model and CLI wiring evidence from the workspace."""
    workspace = get_workspace()
    try:
        main_source, main_path = _read_static_source(workspace, "main.py")
        toml_source, toml_path = _read_static_source(workspace, "omniagent.toml")
        agent_path = workspace.display(workspace.resolve("agent.py"))
        fallback, fallback_line = _builtin_model(workspace)
        configured, config_line = _configured_model(toml_source)
        flag_line, forwarding_line, resolve_line = _cli_model_lines(main_source)
    except (
        SandboxError,
        OSError,
        SyntaxError,
        TypeError,
        ValueError,
        tomllib.TOMLDecodeError,
    ) as exc:
        return f"Error: cannot inspect default model and CLI wiring: {exc}"

    return "\n".join(
        [
            "Default model and CLI evidence:",
            f"{agent_path}:{fallback_line}: built-in DEFAULT_MODEL = {fallback!r}",
            f"{toml_path}:{config_line}: configured [defaults].model = {configured!r}",
            f"{main_path}:{flag_line}: parser declares --model",
            f"{main_path}:{forwarding_line}: cli_settings forwards args.model",
            f"{main_path}:{resolve_line}: resolve() receives cli_settings(args) as CLI overrides",
            (
                "The layer report shows command line last, so an explicit --model "
                "overrides the configured default."
            ),
        ]
    )


def file_info(path: str) -> str:
    """Report a file's size and line count without returning its contents.

    Exists because the alternative is worse. Asked how many lines a file had,
    the agent used to read the whole thing, and on a small context window that
    one observation pushed the system prompt out of the window -- after which a
    7B model answered a completely different question. The number was never
    worth the whole file.
    """
    workspace = get_workspace()
    try:
        facts = workspace.describe(path)
    except SandboxError as exc:
        return f"Error: {exc}"
    except OSError as exc:
        return f"Error: could not inspect {path!r}: {exc.strerror or exc}"

    if facts.binary:
        return f"{facts.path}: {facts.size_bytes:,} bytes, binary (not a text file)"
    if facts.lines == 0:
        return f"{facts.path}: 0 lines, {facts.size_bytes:,} bytes (empty)"
    return (
        f"{facts.path}: {facts.lines:,} lines, {facts.size_bytes:,} bytes\n"
        f"  first line: {facts.first_line[:160]}\n"
        f"  last line : {facts.last_line[:160]}"
    )


class FileInfoArgs(ToolArgs):
    path: str = Field(
        min_length=1,
        max_length=1_000,
        description="Path relative to the workspace root, e.g. 'README.md'.",
    )


class ConfigPrecedenceArgs(ToolArgs):
    path: str = Field(
        min_length=1,
        max_length=1_000,
        description="",
    )


def _run_file_info(args: FileInfoArgs) -> str:
    return file_info(args.path)


def _run_config_precedence(args: ConfigPrecedenceArgs) -> str:
    return inspect_config_precedence(args.path)


TOOLS["file_info"] = Tool(
    name="file_info",
    description=(
        "Report bytes, line count, and first/last lines WITHOUT returning the file. "
        "Use this, not read_file, for size/length/edge-line questions; read_file for contents."
    ),
    args_model=FileInfoArgs,
    run=_run_file_info,
    example="README.md",
)


TOOLS["inspect_config_precedence"] = Tool(
    name="inspect_config_precedence",
    description="Read static config layer order.",
    args_model=ConfigPrecedenceArgs,
    run=_run_config_precedence,
    example="",
    bare_field="path",
)


TOOLS["read_file"] = Tool(
    name="read_file",
    description=(
        "Read workspace text with line numbers. For long files, use JSON path, "
        "start_line, and end_line to read at most 100 relevant lines; oversized full "
        "reads are refused, not shortened. Use file_info for size facts and search_text "
        "to locate text. Outside paths, hidden files, hard links, and credentials are refused."
    ),
    args_model=ReadFileArgs,
    run=_run_read_file,
    example="README.md",
    bare_field="path",
)

TOOLS["list_directory"] = Tool(
    name="list_directory",
    description=(
        "List workspace entries; defaults to the workspace root."
    ),
    args_model=ListDirectoryArgs,
    run=_run_list_directory,
    example=".",
)

TOOLS["search_text"] = Tool(
    name="search_text",
    description=(
        "Find literal text and return file:line matches. This is substring search, not regex."
    ),
    args_model=SearchTextArgs,
    run=_run_search_text,
    example='{"query": "def main", "path": "."}',
)
