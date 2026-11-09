"""A held-out run record contains measurements, never the answer key."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import holdout_eval
from eval_scoring import Verdict
from holdout_eval import (
    PROJECT,
    _append_question_record,
    _tree_clean,
    main,
    question_record,
)


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
        main(["--report"])
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
