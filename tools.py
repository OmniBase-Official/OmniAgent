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
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

import observability as obs
from sandbox import (
    _BINARY_SNIFF_BYTES,
    MAX_READ_CHARS,
    TRUNCATION_NOTE,
    SandboxError,
    get_workspace,
)

_log = obs.get_logger("tools")

#: The stable part of the sandbox's truncation note, used to spot a capped read.
_TRUNCATION_PREFIX = TRUNCATION_NOTE.split("{", 1)[0].rstrip()

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


def read_file(path: str) -> str:
    """Return a file's contents, numbered by line, from inside the workspace."""
    workspace = get_workspace()
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
        f"start of it would not tell you what the rest contains. Use file_info for its "
        f"size, first line and last line, or search_text to find something inside it."
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
    return read_file(args.path)


def _run_list_directory(args: ListDirectoryArgs) -> str:
    return list_directory(args.path)


def _run_search_text(args: SearchTextArgs) -> str:
    return search_text(args.query, args.path)


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


def _run_file_info(args: FileInfoArgs) -> str:
    return file_info(args.path)


TOOLS["file_info"] = Tool(
    name="file_info",
    description=(
        "Report how many lines and bytes a file has, plus its first line and its "
        "LAST line, WITHOUT returning the file. Use this -- not read_file -- for "
        "any question about how long or how big a file is, which of two files is "
        "longer, or what its first or last line says. It is far cheaper than "
        "read_file and cannot overflow the context. Only use read_file when you "
        "need the text in the middle of the file."
    ),
    args_model=FileInfoArgs,
    run=_run_file_info,
    example="README.md",
)


TOOLS["read_file"] = Tool(
    name="read_file",
    description=(
        "Read a short text file from the workspace and return it with line numbers. "
        "Use it when the user asks what is in a file. A file too long to return in "
        "full is refused outright rather than shortened, because the start of a file "
        "cannot tell you what the rest of it contains: use file_info for a file's "
        "size, first line and last line, and search_text to find something inside a "
        "long one. Paths are relative to the workspace root; files outside it, hidden "
        "files and credentials cannot be read."
    ),
    args_model=ReadFileArgs,
    run=_run_read_file,
    example="README.md",
)

TOOLS["list_directory"] = Tool(
    name="list_directory",
    description=(
        "List the files and folders in a workspace directory. Use it to find "
        "out what exists before reading a file. Defaults to the workspace root."
    ),
    args_model=ListDirectoryArgs,
    run=_run_list_directory,
    example=".",
)

TOOLS["search_text"] = Tool(
    name="search_text",
    description=(
        "Find a literal piece of text in the files under a path, returning "
        "file:line matches. Use it to locate where something is mentioned. "
        "This is a plain substring search, NOT a regular expression."
    ),
    args_model=SearchTextArgs,
    run=_run_search_text,
    example='{"query": "def main", "path": "."}',
)
