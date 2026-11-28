"""Safe arithmetic expression evaluation for the calculate tool."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable

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
