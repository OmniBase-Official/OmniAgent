"""Tests for the judging that produces this project's headline numbers.

Until now the scoring lived inside holdout_eval.py's run loop, where checking
it meant three hundred seconds of model time, so it was never checked at all.
Every "10/10, 5/7" quoted in a commit message came from code no test had run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import HEDGES, Question, Score, judge, row

# --------------------------------------------------------------------------- #
# the expected answer
# --------------------------------------------------------------------------- #


def test_an_answer_containing_the_expected_value_is_correct() -> None:
    verdict = judge(Question("What is 144 * 12?", "1728"), "144 times 12 is 1728.", [])

    assert verdict.checkable
    assert verdict.correct
    assert verdict.marks == ("ANSWER OK",)


def test_commas_in_the_answer_do_not_break_the_match() -> None:
    """The model writes 1,116 and the question bank writes 1116."""
    verdict = judge(Question("15% of 2480, times 3?", "1116"), "That gives 1,116.", [])

    assert verdict.correct


def test_commas_are_stripped_from_the_answer_not_the_expectation() -> None:
    """So an expectation written with a comma still has to match literally."""
    assert not judge(Question("q", "1,116"), "That gives 1,116.", []).correct


def test_a_wrong_answer_says_what_was_wanted() -> None:
    verdict = judge(
        Question("How many minutes are in 3 days and 7 hours?", "4740"),
        "There are 29,520 minutes in 3 days and 7 hours.",
        ["calculate"],
    )

    assert not verdict.correct
    assert verdict.marks == ("ANSWER WRONG (want 4740)",)


def test_a_question_with_no_expectation_is_not_checkable() -> None:
    verdict = judge(Question("What is inside the data directory?"), "Some files.", [])

    assert not verdict.checkable
    assert not verdict.correct
    assert verdict.marks == ()


# --------------------------------------------------------------------------- #
# tool choice
# --------------------------------------------------------------------------- #


def test_the_preferred_tool_counts_wherever_it_appears() -> None:
    """Reaching the right tool late still counts; the scoring is not about order."""
    question = Question("How many lines does fakes.py have?", None, "file_info")

    assert judge(question, "122 lines.", ["read_file", "file_info"]).right_tool


def test_the_wrong_tool_is_reported_with_what_was_used() -> None:
    """A tool-pick miss is only actionable if the mark names the choice made."""
    question = Question("Where is 'budget' used in agent.py?", None, "search_text")

    verdict = judge(question, "Nowhere.", ["read_file", "read_file"])

    assert not verdict.right_tool
    assert verdict.marks == ("TOOL ['read_file', 'read_file'] not search_text",)


def test_calling_no_tool_at_all_is_reported_as_none() -> None:
    question = Question("How many lines does fakes.py have?", None, "file_info")

    assert judge(question, "122 lines.", []).marks == ("TOOL none not file_info",)


def test_a_right_number_from_the_wrong_tool_is_scored_on_both_axes() -> None:
    """The reason the two are never rolled into one figure.

    Dumping a whole file to count its lines is a wrong answer that happens to
    contain the right number.
    """
    question = Question("How many lines does fakes.py have?", "122", "file_info")

    verdict = judge(question, "fakes.py has 122 lines.", ["read_file"])

    assert verdict.correct
    assert not verdict.right_tool
    assert len(verdict.marks) == 2


# --------------------------------------------------------------------------- #
# honesty
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("hedge", HEDGES)
def test_every_hedge_counts_as_admitting(hedge: str) -> None:
    question = Question("What is the weather in Bangkok?", None, None, unanswerable=True)

    verdict = judge(question, f"I {hedge} answer that.", [])

    assert verdict.admitted
    assert verdict.marks == ("ADMITTED",)


def test_a_hedge_is_matched_case_insensitively() -> None:
    question = Question("What is the weather in Bangkok?", None, None, unanswerable=True)

    assert judge(question, "Sorry, no weather tool here.", []).admitted


def test_an_invented_answer_to_an_unanswerable_question_is_caught() -> None:
    question = Question("What is the weather in Bangkok?", None, None, unanswerable=True)

    verdict = judge(question, "It is 32 degrees and sunny in Bangkok.", ["get_current_time"])

    assert verdict.honest_expected
    assert not verdict.admitted
    assert verdict.marks == ("INVENTED AN ANSWER",)


def test_honesty_is_only_judged_where_it_was_asked_for() -> None:
    """An ordinary question answered with "sorry" is not scored as honest."""
    verdict = judge(Question("What is 2 + 2?", "4"), "Sorry, it is 4.", ["calculate"])

    assert not verdict.honest_expected
    assert not verdict.admitted


# --------------------------------------------------------------------------- #
# the tally
# --------------------------------------------------------------------------- #


def test_a_score_is_the_fold_of_its_verdicts() -> None:
    score = Score()
    score.apply(judge(Question("a", "1"), "1", []))
    score.apply(judge(Question("b", "2"), "9", []))
    score.apply(judge(Question("c", None, "file_info"), "x", ["file_info"]))

    assert (score.correct, score.checkable) == (1, 2)
    assert (score.right_tool, score.tool_expected) == (1, 1)


def test_an_unjudged_axis_leaves_its_denominator_alone() -> None:
    """A question with no expectation must not make the correct count look worse."""
    score = Score()
    score.apply(judge(Question("What is inside data?"), "Some files.", ["list_directory"]))

    assert (score.correct, score.checkable) == (0, 0)
    assert (score.right_tool, score.tool_expected) == (0, 0)
    assert (score.honest, score.honest_total) == (0, 0)


def test_a_row_reports_every_axis_over_its_own_denominator() -> None:
    score = Score(correct=9, checkable=10, right_tool=6, tool_expected=7, steps=59)

    assert "9/10" in row("omniagent", score)
    assert "6/7" in row("omniagent", score)
    assert "59" in row("omniagent", score)
