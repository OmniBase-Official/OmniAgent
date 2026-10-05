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


# --------------------------------------------------------------------------- #
# a Final Answer stops where the next block starts
# --------------------------------------------------------------------------- #


def test_a_final_answer_is_cut_before_a_block_the_model_tacked_on() -> None:
    """Everything after "Final Answer:" used to become the answer.

    Measured in a session where history had accumulated, the agent answered
    question 5 with the raw text "Thought: I need to calculate 2480 * 15% and
    then multiply that result by 3.\nAction: calculate" -- question 1's plan,
    recycled, and handed to the user as prose. The reply was a Final Answer
    marker followed immediately by a fresh block, and `(.*)` under DOTALL
    swallowed all of it.
    """
    step = _parse("Thought: done\nFinal Answer: 4\nAction: calculate\nAction Input: 2+2")

    assert step.final_answer == "4"


def test_a_final_answer_keeps_its_own_later_lines() -> None:
    """Only a new block ends it, not a newline: answers can be several lines."""
    step = _parse("Final Answer: first line\nsecond line\n\nthird line")

    assert step.final_answer == "first line\nsecond line\n\nthird line"


def test_a_final_answer_is_cut_before_a_leaked_observation() -> None:
    step = _parse("Final Answer: 122 lines.\nObservation: fakes.py: 122 lines")

    assert step.final_answer == "122 lines."


def test_a_final_answer_marker_followed_by_a_new_block_is_not_an_answer() -> None:
    """There is no answer there, so the loop must not present one.

    Falling through to the Action means the model's actual intent -- to keep
    working -- is honoured, and a reply with no Action at all reaches the
    format correction instead of showing the user protocol text.
    """
    step = _parse("Final Answer:\nThought: carry on\nAction: calculate\nAction Input: 2+2")

    assert step.final_answer is None
    assert step.action == "calculate"
    assert step.action_input == "2+2"


def test_a_final_answer_marker_with_nothing_usable_after_it_is_a_violation() -> None:
    step = _parse("Final Answer:\nThought: I am still thinking.")

    assert step.final_answer is None
    assert step.action is None


# --------------------------------------------------------------------------- #
# the answer written into the Action slot
# --------------------------------------------------------------------------- #


def test_final_answer_named_as_an_action_is_an_answer() -> None:
    """Measured on the demo path, which session_eval does not exercise.

    Asked where 'budget' is used in agent.py, the agent searched, found it,
    and replied "Thought: ...\nAction: Final Answer". The parser dispatched a
    tool called "Final Answer", the loop logged tool.unknown, a step was spent
    on nothing and the eventual answer was worse for it. The model is naming
    the marker in the slot it has been taught to put a verb in.
    """
    step = _parse("Thought: done\nAction: Final Answer\nAction Input: 42")

    assert step.final_answer == "42"
    assert step.action is None


@pytest.mark.parametrize("named", ["Final Answer", "final_answer", "FINAL ANSWER", "finalanswer"])
def test_the_marker_is_recognised_however_it_is_spelled(named: str) -> None:
    step = _parse(f"Thought: done\nAction: {named}\nAction Input: 42")

    assert step.final_answer == "42"


def test_the_marker_as_an_action_with_no_input_is_a_format_violation() -> None:
    """There is no answer there, so none is invented from the Thought.

    This is the reply that was actually measured: the marker in the Action
    slot and no Action Input at all. Falling through to the loop's format
    correction costs the same one step as the bogus tool call did, and does
    not put a tool that does not exist into the log.
    """
    step = _parse("Thought: I have found where 'budget' is used.\nAction: Final Answer")

    assert step.final_answer is None
    assert step.action is None


def test_a_real_tool_name_is_still_a_tool() -> None:
    step = _parse("Thought: look\nAction: file_info\nAction Input: agent.py")

    assert step.action == "file_info"
    assert step.final_answer is None
