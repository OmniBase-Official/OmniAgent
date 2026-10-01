"""Tests for the ReAct output parser.

These cover the shapes a small open-source model actually emits, which is where
the loop is most likely to break.
"""

from __future__ import annotations

import pytest

from agent import _parse


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


def test_parse_multiline_final_answer() -> None:
    step = _parse("Thought: Done.\nFinal Answer: line one\nline two")
    assert step.final_answer == "line one\nline two"


def test_parse_tolerates_inline_call() -> None:
    step = _parse("Thought: maths\nAction: calculate(2 + 2)")
    assert step.action == "calculate"
    assert step.action_input == "2 + 2"


@pytest.mark.parametrize(
    "raw_input",
    ["```\n2 + 2\n```", "```python\n2 + 2\n```", '"2 + 2"', "'2 + 2'", "`2 + 2`"],
)
def test_parse_tolerates_code_fences_and_quotes(raw_input: str) -> None:
    step = _parse(f"Thought: maths\nAction: calculate\nAction Input: {raw_input}")
    assert step.action_input == "2 + 2"


@pytest.mark.parametrize("placeholder", ["none", "(none)", "<none>", "[none]", "N/A", "-", ""])
def test_parse_no_arg_tool(placeholder: str) -> None:
    step = _parse(f"Thought: need date\nAction: get_current_time\nAction Input: {placeholder}")
    assert step.action == "get_current_time"
    assert step.action_input == ""


@pytest.mark.parametrize(
    "decorated",
    ["calculate", "**calculate**", "`calculate`", "[calculate]", "calculate.", "  calculate  "],
)
def test_parse_strips_action_name_decorations(decorated: str) -> None:
    step = _parse(f"Thought: maths\nAction: {decorated}\nAction Input: 1 + 1")
    assert step.action == "calculate"


def test_parse_is_case_insensitive() -> None:
    step = _parse("thought: maths\naction: calculate\naction input: 1 + 1")
    assert step.action == "calculate"
    assert step.action_input == "1 + 1"


def test_parse_final_answer_wins_over_action() -> None:
    """A reply holding both must not fire a tool after the answer is given."""
    step = _parse("Thought: done\nFinal Answer: 4\nAction: calculate\nAction Input: 2+2")
    assert step.final_answer is not None
    assert step.action is None


def test_parse_stops_action_input_at_the_next_marker() -> None:
    step = _parse(
        "Thought: maths\nAction: calculate\nAction Input: 2 + 2\nObservation: 2 + 2 = 4"
    )
    assert step.action_input == "2 + 2"


def test_parse_unparseable_reply() -> None:
    step = _parse("Sure! The answer is probably 4.")
    assert step.action is None
    assert step.final_answer is None
    assert step.raw == "Sure! The answer is probably 4."


def test_parse_empty_reply() -> None:
    step = _parse("")
    assert step.action is None
    assert step.final_answer is None
    assert step.thought == ""
