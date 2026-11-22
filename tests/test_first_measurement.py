"""The first-pass runner's grader must read the answer, never the banner.

The first measurement scored 4 of 4 and one of the four was wrong: the
expectation "12" matched 127.0.0.1 in the endpoint line main.py prints above
the answer. These tests hold that regression and the trace parser.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from first_measurement import answer_region, grade, parse_trace

BANNER = (
    "    workspace: D:\\somewhere\\tree\n"
    "    endpoint : http://127.0.0.1:11434/v1\n"
    "    model    : omniagent-v2:latest\n"
)


def _output(answer: str, trace: str = "") -> str:
    return f"{BANNER}\n{trace}\nOmniAgent: {answer}\n\n"


def test_a_wrong_answer_is_not_rescued_by_digits_in_the_banner() -> None:
    """The regression: expectation 12, answer 50, banner holding 127.0.0.1."""
    output = _output("There are 50 Python files in the scripts directory.")

    assert "12" in output, "the banner really does carry the expectation"
    assert grade(answer_region(output), "12") is False


def test_a_whole_token_in_the_banner_cannot_satisfy_an_expectation() -> None:
    """The guard the q4 case does not isolate.

    In q4 two guards agree: the answer region excludes the banner, and the
    token boundary rejects ``12`` inside ``127``. Remove either and that test
    stays green, so it cannot prove either. Here the banner carries the
    expectation as a whole token (the port), so only reading the answer region
    alone can reject it.
    """
    output = _output("There are 50 Python files in the scripts directory.")

    assert grade(output, "11434") is True, "graded whole, the banner would pass it"
    assert grade(answer_region(output), "11434") is False


def test_a_right_answer_is_still_scored_right() -> None:
    output = _output("There are 12 Python files in the scripts directory.")

    assert grade(answer_region(output), "12") is True


def test_an_expectation_inside_a_longer_number_does_not_count() -> None:
    assert grade("There are 120 files.", "12") is False
    assert grade("Version 3.12 shipped.", "12") is False


def test_an_empty_answer_is_blank_not_wrong_and_not_right() -> None:
    """exit code 0 with nothing printed after the prefix must stay visible."""
    output = f"{BANNER}\nOmniAgent: \n\n"

    assert answer_region(output) == ""
    assert grade(answer_region(output), "12") is False


def test_no_answer_prefix_at_all_yields_a_blank_region() -> None:
    assert answer_region(BANNER) == ""


def test_the_trace_yields_tool_names_steps_and_tool_errors() -> None:
    trace = (
        "\n  [step 1]\n  Thought      : look\n  Action       : list_directory\n"
        "  Action Input : scripts\n  Observation  : a.py\n"
        "\n  [step 2]\n  Action       : count_lines\n  Action Input : x\n"
        "  Observation  : Error: tool is not allowed for this task.\n"
    )

    parsed = parse_trace(_output("", trace))

    assert parsed.steps == 2
    assert parsed.tools == ["list_directory", "count_lines"]
    assert parsed.tool_errors == 1
