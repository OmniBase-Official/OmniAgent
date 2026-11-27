"""A held-out run record contains measurements, never the answer key.

Ported from the legacy line (brief 12), with one deliberate change: the CLI flag
that prints this summary is ``--runs-report``, because ``--report`` on the
canonical line already means "destination of the sanitized promotion report".
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import holdout_eval
import session_eval
from eval_scoring import Verdict, judge
from holdout_eval import (
    PROJECT,
    _append_question_record,
    _tree_clean,
    main,
    question_record,
)

from agent import AgentConfig, ReActAgent
from sandbox import get_workspace, set_workspace
from tests.fakes import FakeOpenAI


def test_question_record_has_only_index_tools_steps_and_verdict_booleans() -> None:
    verdict = Verdict(
        checkable=True,
        correct=True,
        tool_expected=True,
        right_tool=False,
        honest_expected=False,
        admitted=False,
    )

    record = question_record(7, verdict, 4, ["read_file", "search_text"])

    assert record == {
        "index": 7,
        "tools": ["read_file", "search_text"],
        "steps": 4,
        "checkable": True,
        "correct": True,
        "tool_expected": True,
        "right_tool": False,
        "honest_expected": False,
        "admitted": False,
    }
    assert not {"question", "text", "expect", "expectation"} & record.keys()


def test_appended_run_record_carries_cleanliness_separately(tmp_path: Path) -> None:
    path = tmp_path / "runs.jsonl"
    measurement = question_record(
        7,
        Verdict(True, True, True, True, True, True),
        4,
        ["read_file"],
    )

    _append_question_record(measurement, "fixture-model", "abc1234", True, path)

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["clean"] is True
    assert stored["commit"] == "abc1234"
    assert "clean" not in measurement


def test_tree_cleanliness_is_unknown_when_git_status_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = Mock(return_value=Mock(stdout="", returncode=0))
    monkeypatch.setattr(subprocess, "run", runner)

    assert _tree_clean() is True
    command = runner.call_args.args[0]
    options = runner.call_args.kwargs
    assert command == ["git", "-C", str(PROJECT), "status", "--porcelain"]
    assert options["check"] is True
    assert options["timeout"] == 10
    assert "shell" not in options

    runner.return_value = Mock(stdout=" M scripts/holdout_eval.py\n", returncode=0)
    assert _tree_clean() is False

    runner.side_effect = FileNotFoundError("git unavailable")
    assert _tree_clean() == "unknown"


def _run_record(index: int, commit: str, clean: object) -> dict[str, object]:
    return {
        "index": index,
        "commit": commit,
        "clean": clean,
        "model": "fixture-model",
        "steps": 2,
        "checkable": True,
        "correct": True,
        "tool_expected": True,
        "right_tool": True,
        "honest_expected": True,
        "admitted": True,
    }


def _write_runs(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )


def test_report_drops_and_counts_dirty_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "runs.jsonl"
    _write_runs(path, [_run_record(2, "a1", True), _run_record(2, "a1", False)])

    main_report_path = holdout_eval.RUNS_PATH
    holdout_eval.RUNS_PATH = path
    try:
        main(["--runs-report"])
    finally:
        holdout_eval.RUNS_PATH = main_report_path

    output = capsys.readouterr().out
    assert "2 records, 1 dropped (1 dirty, 0 unknown)" in output
    assert "question 2: 1 run(s)" in output
    assert "commit a1: 2 records, 1 clean, 1 dropped" in output


def test_report_treats_missing_and_unknown_cleanliness_as_dropped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "runs.jsonl"
    missing = _run_record(5, "a1", True)
    missing.pop("clean")
    _write_runs(path, [missing, _run_record(5, "a1", "unknown")])

    holdout_eval.report(path)

    output = capsys.readouterr().out
    assert "2 records, 2 dropped (0 dirty, 2 unknown)" in output
    assert "2 unknown (1 missing field)" in output
    assert "question 5: no surviving runs" in output


def test_report_keeps_commit_groups_separate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "runs.jsonl"
    passing = _run_record(3, "commit-a", True)
    failing = _run_record(3, "commit-b", True)
    failing["correct"] = False
    _write_runs(path, [passing, failing])

    holdout_eval.report(path)

    output = capsys.readouterr().out
    assert "2 commit groups; each is reported separately." in output
    assert "commit commit-a: 1 record, 1 clean, 0 dropped" in output
    assert "commit commit-b: 1 record, 1 clean, 0 dropped" in output
    assert "answer=1/1" in output
    assert "answer=0/1" in output
    assert "2/2" not in output


def test_report_names_questions_with_no_surviving_runs_without_zero_over_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "runs.jsonl"
    _write_runs(path, [_run_record(4, "commit-a", False), _run_record(8, "commit-a", False)])

    holdout_eval.report(path)

    output = capsys.readouterr().out
    assert "question 4: no surviving runs" in output
    assert "question 8: no surviving runs" in output
    assert "0/0" not in output


# --------------------------------------------------------------------------- #
# what the port added: the wiring, the flag, the two record files, the denominator
# --------------------------------------------------------------------------- #


def _wire_fake_agent(monkeypatch: pytest.MonkeyPatch, replies: list[str]) -> FakeOpenAI:
    """Run ``evaluate`` against a fake client; no model server is contacted."""
    fake = FakeOpenAI(replies=replies)
    real = ReActAgent  # the class itself, never a factory left by an earlier call

    def factory(config: AgentConfig, printer: Callable[[str], None]) -> ReActAgent:
        return real(config=config, printer=printer, client=fake.as_client())

    monkeypatch.setattr("holdout_eval.ReActAgent", factory)
    return fake


@pytest.fixture
def restored_workspace() -> Iterator[None]:
    """``evaluate`` swaps the process-wide workspace and never puts it back."""
    original = get_workspace()
    yield
    set_workspace(original)


def _total_questions() -> int:
    return sum(len(session) for session in holdout_eval.SESSIONS_UNDER_TEST)


def _read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_evaluate_appends_one_individual_record_per_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restored_workspace: None
) -> None:
    runs = tmp_path / "runs.jsonl"
    _wire_fake_agent(monkeypatch, ["Thought: done\nFinal Answer: ok"] * _total_questions())
    monkeypatch.setattr(holdout_eval, "_short_commit", lambda: "abc1234")
    monkeypatch.setattr(holdout_eval, "_tree_clean", lambda: True)

    holdout_eval.evaluate("fixture-model", runs_path=runs)

    records = _read(runs)
    assert [r["index"] for r in records] == list(range(_total_questions()))
    assert {r["commit"] for r in records} == {"abc1234"}
    assert {r["model"] for r in records} == {"fixture-model"}
    assert all(r["clean"] is True for r in records)


def test_evaluate_records_a_dirty_or_unknown_tree_as_such(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restored_workspace: None
) -> None:
    """Me's test at the wiring level: the field must reach the file, not just the builder."""
    monkeypatch.setattr(holdout_eval, "_short_commit", lambda: "abc1234")
    for state in (False, "unknown"):
        runs = tmp_path / f"runs-{state}.jsonl"
        _wire_fake_agent(monkeypatch, ["Thought: done\nFinal Answer: ok"] * _total_questions())
        monkeypatch.setattr(holdout_eval, "_tree_clean", lambda state=state: state)

        holdout_eval.evaluate("fixture-model", runs_path=runs)

        assert {r["clean"] for r in _read(runs)} == {state}


def test_evaluate_records_carry_no_question_answer_or_expectation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, restored_workspace: None
) -> None:
    runs = tmp_path / "runs.jsonl"
    canary = "ANSWER-CANARY-7731"
    _wire_fake_agent(monkeypatch, [f"Thought: done\nFinal Answer: {canary}"] * _total_questions())
    monkeypatch.setattr(holdout_eval, "_short_commit", lambda: "abc1234")
    monkeypatch.setattr(holdout_eval, "_tree_clean", lambda: True)

    holdout_eval.evaluate("fixture-model", runs_path=runs)

    blob = runs.read_text(encoding="utf-8")
    assert canary not in blob
    for session in holdout_eval.SESSIONS_UNDER_TEST:
        for question in session:
            assert question.text not in blob
            if question.expect and len(question.expect) >= 12:
                assert question.expect not in blob


def test_the_two_evaluations_write_different_run_files() -> None:
    """Both modules call their constant RUNS_PATH, so equal values would interleave records.

    A holdout record has an ``index`` and no ``arrangement``; a session record has the
    reverse. Pooled into one file each reader would silently misread the other's rows.
    """
    assert holdout_eval.RUNS_PATH != session_eval.RUNS_PATH
    assert holdout_eval.RUNS_PATH.parent == session_eval.RUNS_PATH.parent


def test_the_summary_flag_does_not_take_over_the_promotion_report_flag() -> None:
    with pytest.raises(SystemExit):
        main(["--report", "out.json"])  # still means "destination", still needs a run
    with pytest.raises(SystemExit):
        main(["--runs-report", "some-model"])
    with pytest.raises(SystemExit):
        main(["--runs-report", "--promotion-run", "run"])


def test_the_report_states_the_denominator_it_is_a_baseline_for(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """No figure from before 2026-11-22 is comparable; the report says so itself."""
    path = tmp_path / "runs.jsonl"
    _write_runs(path, [_run_record(0, "a1", True)])

    holdout_eval.report(path)

    output = capsys.readouterr().out
    verdicts = [
        judge(question, "", [])
        for session in holdout_eval.SESSIONS_UNDER_TEST
        for question in session
    ]
    assert f"bank: {len(verdicts)} questions" in output
    assert f"{sum(v.checkable for v in verdicts)} answer-checked" in output
    assert "not comparable with any figure recorded before 2026-11-22" in output


DEEP_RUN_RECORD = "[" * 3_000 + "]" * 3_000
TOO_DEEP = "run records have JSON nesting that is too deep to read"


def test_the_deep_record_really_overflows_the_parser(
    parsers_overflow_on_hostile_input: None,
) -> None:
    """The proving test: without this the guard tests below could be passing on nothing."""
    with pytest.raises(RecursionError):
        json.loads(DEEP_RUN_RECORD)


@pytest.mark.usefixtures("parsers_overflow_on_hostile_input")
def test_a_run_record_nested_too_deep_is_refused_with_fixed_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "runs.jsonl"
    path.write_text(DEEP_RUN_RECORD + "\n", encoding="utf-8")
    monkeypatch.setattr(holdout_eval, "RUNS_PATH", path)

    with pytest.raises(SystemExit) as direct:
        holdout_eval._read_run_records(path)
    with pytest.raises(SystemExit) as entry:
        main(["--runs-report"])

    assert direct.value.code == entry.value.code == TOO_DEEP
    captured = capsys.readouterr()
    assert "RecursionError" not in captured.out + captured.err
    assert "recursion" not in (captured.out + captured.err).lower()
