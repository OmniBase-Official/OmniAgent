"""Tests for the evaluation that measures what a long conversation costs.

The point of the script is that exactly one thing differs between its two
passes, so these assert that one thing: whether the question before is in the
prompt. Without that, "accumulated" and "isolated" would be two names for the
same run and any difference between their scores would mean nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from itertools import pairwise

from eval_scoring import Score, Verdict
from session_eval import WALK, Outcome, _passed, drift, run_walk

from tests.fakes import FakeOpenAI

ANSWERED = "Thought: I know this\nFinal Answer: done"


def _fake() -> FakeOpenAI:
    return FakeOpenAI(replies=[ANSWERED] * len(WALK))


# --------------------------------------------------------------------------- #
# the one variable
# --------------------------------------------------------------------------- #


def test_the_accumulated_pass_carries_the_earlier_questions() -> None:
    fake = _fake()

    run_walk("fake", shared_history=True, client=fake.as_client())

    second = [str(message["content"]) for message in fake.calls[1]["messages"]]
    assert any(WALK[0].text in content for content in second), (
        "question 2 was asked without question 1 in history"
    )


def test_the_isolated_pass_starts_each_question_clean() -> None:
    fake = _fake()

    run_walk("fake", shared_history=False, client=fake.as_client())

    second = [str(message["content"]) for message in fake.calls[1]["messages"]]
    assert not any(WALK[0].text in content for content in second), (
        "a fresh agent still saw the previous question"
    )


def test_both_passes_ask_every_question_once() -> None:
    for shared in (True, False):
        fake = _fake()
        outcome = run_walk("fake", shared_history=shared, client=fake.as_client())
        assert outcome.score.asked == len(WALK)
        assert len(outcome.verdicts) == len(WALK)


def test_only_the_accumulated_pass_reports_follow_ups() -> None:
    """In the isolated pass every question is a first question."""
    isolated = run_walk("fake", shared_history=False, client=_fake().as_client())
    accumulated = run_walk("fake", shared_history=True, client=_fake().as_client())

    assert isolated.score.follow_total == 0
    assert accumulated.score.follow_total == len(WALK) - 1


# --------------------------------------------------------------------------- #
# the walk itself
# --------------------------------------------------------------------------- #


def test_the_walk_exercises_every_axis() -> None:
    """A walk that only checked one axis could not show where drift lands."""
    assert any(question.expect for question in WALK)
    assert any(question.prefer_tool for question in WALK)
    assert any(question.unanswerable for question in WALK)


def test_the_walk_changes_topic_between_questions() -> None:
    """The drift being measured is the previous topic bleeding into the next.

    A walk of eight arithmetic questions would never provoke it, so no two
    neighbouring questions ask for the same tool.
    """
    wanted = [question.prefer_tool for question in WALK]
    assert all(before != after or before is None for before, after in pairwise(wanted))


# --------------------------------------------------------------------------- #
# reading the difference
# --------------------------------------------------------------------------- #


def _outcome(verdicts: list[Verdict]) -> Outcome:
    return Outcome(score=Score(), verdicts=verdicts)


PASS = Verdict(checkable=True, correct=True)
FAIL = Verdict(checkable=True, correct=False)
NOTHING_TO_CHECK = Verdict()


def test_a_question_lost_to_history_is_reported() -> None:
    before = [PASS] * len(WALK)
    after = [PASS] * len(WALK)
    after[3] = FAIL

    moved = drift(_outcome(before), _outcome(after))

    assert [(position, direction) for position, _, direction in moved] == [
        (4, "LOST with history")
    ]


def test_a_question_gained_with_history_is_reported_too() -> None:
    """Not a win to bank: the same instability, pointing the other way.

    Restating the question after every observation turned one REPL question
    from twelve steps and a wrong answer into four and a right one, and cost
    two arithmetic answers on the held-out set. A gain that a single run
    cannot tell from noise has to be printed as plainly as a loss.
    """
    before = [PASS] * len(WALK)
    before[1] = FAIL

    moved = drift(_outcome(before), _outcome([PASS] * len(WALK)))

    assert [(position, direction) for position, _, direction in moved] == [
        (2, "GAINED with history")
    ]


def test_a_walk_that_did_not_move_reports_nothing() -> None:
    assert drift(_outcome([PASS] * len(WALK)), _outcome([PASS] * len(WALK))) == []


def test_a_question_with_nothing_to_check_cannot_be_the_thing_that_moved() -> None:
    """It contributes to no denominator, so it must not count as a change."""
    assert _passed(NOTHING_TO_CHECK)
    assert drift(_outcome([NOTHING_TO_CHECK] * len(WALK)), _outcome([PASS] * len(WALK))) == []


def test_passing_needs_every_axis_the_question_asked_for() -> None:
    """A right answer from the wrong tool has not passed the question."""
    assert not _passed(Verdict(checkable=True, correct=True, tool_expected=True))
    assert not _passed(Verdict(checkable=True, tool_expected=True, right_tool=True))
    assert _passed(Verdict(checkable=True, correct=True, tool_expected=True, right_tool=True))


def test_an_unanswered_honesty_question_does_not_pass() -> None:
    assert not _passed(Verdict(honest_expected=True, admitted=False))
    assert _passed(Verdict(honest_expected=True, admitted=True))
