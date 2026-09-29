"""Offline checks for the parts that do not need a running model.

Covers the tools and the ReAct output parser -- the two places where a small
open-source model is most likely to break things. Run it with either:

    python test_offline.py
    pytest -q test_offline.py
"""

from __future__ import annotations

from agent import _parse
from tools import calculate, get_current_time, run_tool


def test_calculate_basic_arithmetic() -> None:
    assert calculate("2 + 2").endswith("= 4")
    assert calculate("(1250 * 0.07) + 12").endswith("= 99.5")
    assert calculate("10 / 4").endswith("= 2.5")
    assert calculate("2 ** 10").endswith("= 1024")


def test_calculate_functions_and_constants() -> None:
    assert calculate("sqrt(144)").endswith("= 12")
    assert calculate("round(pi, 4)").endswith("= 3.1416")
    assert calculate("max(3, 9, 4)").endswith("= 9")


def test_calculate_rejects_arbitrary_code() -> None:
    for hostile in (
        "__import__('os').system('echo pwned')",
        "open('secret.txt').read()",
        "[].__class__",
        "lambda: 1",
        "9 ** 9 ** 9",
    ):
        assert calculate(hostile).startswith("Error:"), hostile


def test_calculate_handles_bad_input() -> None:
    assert calculate("").startswith("Error:")
    assert calculate("1 / 0").startswith("Error:")
    assert calculate("2 +").startswith("Error:")


def test_calculate_strips_model_decorations() -> None:
    assert calculate("`2 + 2`").endswith("= 4")
    assert calculate("expression=2 + 2").endswith("= 4")


def test_get_current_time_shape() -> None:
    result = get_current_time()
    assert result.startswith("Local time:")
    assert "UTC:" in result


def test_run_tool_dispatch() -> None:
    assert run_tool("calculate", "3 * 3").endswith("= 9")
    assert run_tool("does_not_exist", "").startswith("Error: unknown tool")


def test_parse_action() -> None:
    step = _parse("Thought: I need maths.\nAction: calculate\nAction Input: 2 + 2")
    assert step.thought == "I need maths."
    assert step.action == "calculate"
    assert step.action_input == "2 + 2"
    assert step.final_answer is None


def test_parse_final_answer() -> None:
    step = _parse("Thought: Done.\nFinal Answer: The result is 4.")
    assert step.final_answer == "The result is 4."
    assert step.action is None


def test_parse_tolerates_inline_call() -> None:
    step = _parse("Thought: maths\nAction: calculate(2 + 2)")
    assert step.action == "calculate"
    assert step.action_input == "2 + 2"


def test_parse_tolerates_code_fences_and_quotes() -> None:
    step = _parse('Thought: maths\nAction: calculate\nAction Input: ```\n2 + 2\n```')
    assert step.action_input == "2 + 2"
    step = _parse('Thought: maths\nAction: calculate\nAction Input: "2 + 2"')
    assert step.action_input == "2 + 2"


def test_parse_no_arg_tool() -> None:
    for placeholder in ("none", "(none)", "<none>", "[none]", "N/A", "-", ""):
        step = _parse(
            f"Thought: need date\nAction: get_current_time\nAction Input: {placeholder}"
        )
        assert step.action == "get_current_time", placeholder
        assert step.action_input == "", placeholder


def test_parse_unparseable_reply() -> None:
    step = _parse("Sure! The answer is probably 4.")
    assert step.action is None
    assert step.final_answer is None


def _main() -> int:
    tests = [(name, obj) for name, obj in sorted(globals().items()) if name.startswith("test_")]
    failures = 0
    for name, func in tests:
        try:
            func()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report, do not hide
            failures += 1
            print(f"ERROR {name}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
