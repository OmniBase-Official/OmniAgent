"""Tests for the evaluation that measures what a long conversation costs.

The point of the script is that exactly one thing differs between its two
passes, so these assert that one thing: whether the question before is in the
prompt. Without that, "accumulated" and "isolated" would be two names for the
same run and any difference between their scores would mean nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from itertools import pairwise

from eval_scoring import Score, Verdict
from session_eval import (
    WALK,
    Outcome,
    _is_drift,
    _passed,
    aggregate,
    commit,
    drift,
    read_runs,
    record,
    report,
    run_walk,
)

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


# --------------------------------------------------------------------------- #
# reading several runs together
# --------------------------------------------------------------------------- #


def _run(arrangement: str, passed: list[bool], steps: list[int]) -> dict[str, Any]:
    return {
        "model": "omniagent",
        "arrangement": arrangement,
        "questions": [question.text for question in WALK],
        "passed": passed,
        "steps": steps,
    }


ALL = [True] * len(WALK)
NONE = [False] * len(WALK)
EVEN = [2] * len(WALK)


def test_a_recorded_run_can_be_read_back(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    outcome = run_walk("fake", shared_history=True, client=_fake().as_client())

    record(outcome, "fake", "accumulated", path)

    (row,) = read_runs(path)
    assert row["arrangement"] == "accumulated"
    assert row["questions"] == [question.text for question in WALK]
    assert len(row["steps"]) == len(WALK)


def test_reading_a_file_that_is_not_there_is_not_an_error(tmp_path: Path) -> None:
    """A first run must not have to check whether it is the first."""
    assert read_runs(tmp_path / "nothing.jsonl") == []


def test_runs_are_pooled_by_question_text_not_by_position() -> None:
    """Re-ordering the walk must not merge two different questions' figures."""
    shifted = _run("isolated", ALL, EVEN)
    shifted["questions"] = list(reversed(shifted["questions"]))

    spreads = aggregate([_run("isolated", ALL, EVEN), shifted])

    assert all(spread.runs == 2 for spread in spreads.values())
    assert len(spreads) == len(WALK)


def test_a_spread_counts_the_passes_and_the_step_range() -> None:
    spreads = aggregate(
        [
            _run("isolated", ALL, [2] * len(WALK)),
            _run("isolated", NONE, [9] * len(WALK)),
        ]
    )

    spread = spreads[("isolated", WALK[0].text)]
    assert (spread.passed, spread.runs) == (1, 2)
    assert (spread.steps_low, spread.steps_high) == (2, 9)


def test_a_spread_that_disagreed_with_itself_is_not_settled() -> None:
    """Two runs, two answers: that is the measurement failing, not a result."""
    spreads = aggregate([_run("isolated", ALL, EVEN), _run("isolated", NONE, EVEN)])

    assert not spreads[("isolated", WALK[0].text)].settled


def test_a_spread_is_settled_when_every_run_agreed() -> None:
    spreads = aggregate([_run("isolated", ALL, EVEN)] * 3)

    assert spreads[("isolated", WALK[0].text)].settled


# --------------------------------------------------------------------------- #
# what counts as drift once more than one run is in
# --------------------------------------------------------------------------- #


def test_drift_needs_both_arrangements_to_have_settled() -> None:
    """3/3 against 0/3 is drift; 2/3 against 1/3 has not been shown to be."""
    settled = aggregate(
        [_run("isolated", ALL, EVEN)] * 3 + [_run("accumulated", NONE, EVEN)] * 3
    )
    # Two of three isolated runs passed and no accumulated run did. Without
    # the settled requirement this reads as drift, because one side passed at
    # least once and the other never did -- which is why the discriminating
    # case has to be the asymmetric one. An earlier version of this test used
    # 1/2 against 1/2, where both readings agree and the assertion was empty.
    unsettled = aggregate(
        [_run("isolated", ALL, EVEN)] * 2
        + [_run("isolated", NONE, EVEN)]
        + [_run("accumulated", NONE, EVEN)] * 3
    )
    question = WALK[0].text

    assert _is_drift(settled[("isolated", question)], settled[("accumulated", question)])
    assert not _is_drift(
        unsettled[("isolated", question)], unsettled[("accumulated", question)]
    )


def test_an_arrangement_never_run_is_not_drift() -> None:
    spreads = aggregate([_run("isolated", ALL, EVEN)])

    assert not _is_drift(spreads[("isolated", WALK[0].text)], None)


def test_two_settled_arrangements_that_agree_are_not_drift() -> None:
    spreads = aggregate([_run("isolated", ALL, EVEN), _run("accumulated", ALL, EVEN)])
    question = WALK[0].text

    assert not _is_drift(spreads[("isolated", question)], spreads[("accumulated", question)])


# --------------------------------------------------------------------------- #
# runs of different code are not one measurement
# --------------------------------------------------------------------------- #


def test_a_recorded_run_names_the_code_it_came_from(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    outcome = run_walk("fake", shared_history=True, client=_fake().as_client())

    record(outcome, "fake", "accumulated", path)

    (row,) = read_runs(path)
    assert row["commit"]


def test_the_commit_is_a_short_hash_or_an_admission() -> None:
    """Never a guess: if git cannot be asked, the row says so."""
    version = commit()

    assert version == "unknown" or (4 <= len(version) <= 40 and version.isalnum())


def _runs_file(path: Path, *rows: dict[str, Any]) -> Path:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + chr(10))
    return path


def test_the_report_separates_runs_by_code_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Pooling across versions reports a figure that is true of neither.

    The runs file held three runs of yesterday's agent and one of today's, and
    --report averaged them into one table before this.
    """
    old = _run("accumulated", ALL, EVEN)
    old["commit"] = "aaaa111"
    new_row = _run("accumulated", NONE, EVEN)
    new_row["commit"] = "bbbb222"

    report(_runs_file(tmp_path / "runs.jsonl", old, new_row))

    printed = capsys.readouterr().out
    assert "aaaa111" in printed
    assert "bbbb222" in printed
    assert "2 code versions" in printed


def test_a_run_recorded_before_versions_were_tracked_is_called_unknown(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    row = _run("accumulated", ALL, EVEN)
    row.pop("commit", None)

    report(_runs_file(tmp_path / "runs.jsonl", row))

    assert "unknown" in capsys.readouterr().out


def test_every_walk_question_checks_something_about_the_answer() -> None:
    """A question scored on tool choice alone reads as though it passed.

    Three of the eight carried no expectation until 2026-10-06. The
    data-directory question reached for list_directory in all ten recorded
    runs, which scored 10/10, and described the data directory in four of
    them. Both figures were true and only one of them was being read.
    """
    unchecked = [q.text for q in WALK if q.expect is None and not q.unanswerable]

    assert unchecked == [], unchecked


def test_the_expectations_the_walk_depends_on_are_still_in_the_tree() -> None:
    """Two expectations are facts about this repository, not about the model.

    If agent.py stops containing "agent.budget.exhausted", or data/ stops
    containing collect-run.log, those questions become unanswerable and the
    score falls without the agent having changed. This says so out loud rather
    than letting it look like a regression.
    """
    root = Path(__file__).resolve().parent.parent

    assert "agent.budget.exhausted" in (root / "agent.py").read_text(encoding="utf-8")
    assert (root / "data" / "collect-run.log").exists()
