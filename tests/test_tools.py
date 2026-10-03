"""Tests for the tool implementations and the registry."""

from __future__ import annotations

import pytest

from tools import (
    TOOLS,
    CalculateArgs,
    Tool,
    calculate,
    describe_tools,
    get_current_time,
    run_tool,
    tool_names,
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2 + 2", "4"),
        ("(1250 * 0.07) + 12", "99.5"),
        ("10 / 4", "2.5"),
        ("2 ** 10", "1024"),
        ("17 % 5", "2"),
        ("17 // 5", "3"),
        ("-5 + 3", "-2"),
    ],
)
def test_calculate_basic_arithmetic(expression: str, expected: str) -> None:
    assert calculate(expression).endswith(f"= {expected}")


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("sqrt(144)", "12"),
        ("round(pi, 4)", "3.1416"),
        ("max(3, 9, 4)", "9"),
        ("min(3, 9, 4)", "3"),
        ("abs(-7)", "7"),
        ("factorial(5)", "120"),
        ("log10(1000)", "3"),
    ],
)
def test_calculate_functions_and_constants(expression: str, expected: str) -> None:
    assert calculate(expression).endswith(f"= {expected}")


@pytest.mark.parametrize(
    "hostile",
    [
        "__import__('os').system('echo pwned')",
        "open('secret.txt').read()",
        "[].__class__",
        "lambda: 1",
        "9 ** 9 ** 9",
        "factorial(10 ** 6)",
        "'a' * 10",
        "exec('x=1')",
        "[i for i in range(10)]",
    ],
)
def test_calculate_rejects_arbitrary_code(hostile: str) -> None:
    assert calculate(hostile).startswith("Error:")


@pytest.mark.parametrize(
    "bad",
    ["", "   ", "1 / 0", "2 +", "unknown_name", "nope(1)", "x" * 600],
)
def test_calculate_handles_bad_input(bad: str) -> None:
    assert calculate(bad).startswith("Error:")


@pytest.mark.parametrize("decorated", ["`2 + 2`", "expression=2 + 2", "  2 + 2  "])
def test_calculate_strips_model_decorations(decorated: str) -> None:
    assert calculate(decorated).endswith("= 4")


def test_get_current_time_shape() -> None:
    result = get_current_time()
    assert result.startswith("Local time:")
    assert "UTC:" in result


@pytest.mark.parametrize("junk", ["", "none", "(none)", "today please"])
def test_a_no_arg_tool_ignores_whatever_the_model_sent(junk: str) -> None:
    """get_current_time() takes nothing, so the Action Input is discarded."""
    assert run_tool("get_current_time", junk).startswith("Local time:")


def test_run_tool_dispatch() -> None:
    assert run_tool("calculate", "3 * 3").endswith("= 9")
    assert run_tool("  calculate  ", "3 * 3").endswith("= 9")
    assert run_tool("does_not_exist", "").startswith("Error: there is no tool called")


def test_run_tool_never_raises() -> None:
    """A tool that explodes must come back as an Observation, not an exception."""

    def boom(_args: CalculateArgs) -> str:
        raise RuntimeError("kaboom")

    original = TOOLS["calculate"]
    TOOLS["calculate"] = Tool(
        name="calculate",
        description=original.description,
        args_model=CalculateArgs,
        run=boom,
        example=original.example,
    )
    try:
        result = run_tool("calculate", "1 + 1")
    finally:
        TOOLS["calculate"] = original

    assert result.startswith("Error: tool 'calculate' raised RuntimeError")


def test_registry_is_rendered_into_the_prompt() -> None:
    rendered = describe_tools()
    for name in TOOLS:
        assert name in rendered
        assert name in tool_names()


def test_an_invented_tool_is_told_that_inventing_it_changed_nothing() -> None:
    """Measured: naming a tool that does not exist, then answering anyway.

    Across three recorded runs, asked for the weather in Bangkok with seven
    earlier questions in history, the agent called a tool it had made up --
    get_current_weather -- read the error, and answered "The current
    temperature in Bangkok is 35 degrees Celsius with a relative humidity of
    89%". With a fresh agent the same question is answered honestly in all
    three runs, so the capability to admit it is there; what the error has to
    carry is that a missing tool means missing information, not information to
    supply from somewhere else.

    This text reaches a prompt only once a tool has already been invented, so
    unlike a change to a tool's description it cannot perturb a turn that
    never goes wrong.
    """
    observation = run_tool("get_current_weather", "Bangkok")

    assert observation.startswith("Error:")
    assert "does not create the capability" in observation
    assert "cannot find it out" in observation
    # The list of real tools stays, because the next step may well be one.
    assert "search_text" in observation
