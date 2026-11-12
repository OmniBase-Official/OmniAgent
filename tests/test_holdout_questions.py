"""Tests for the held-out question bank's expectations.

Every question in it carried ``prefer_tool`` and no ``expect`` until
2026-10-06, so the ``correct`` column in the figures quoted for holdout_eval
only ever covered the arithmetic, while the file questions read as though
their answers had passed. These assertions pin the shape of the fix.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import Score
from holdout_eval import (
    SESSIONS_UNDER_TEST,
    _last_line,
    _lines,
    evaluate_promotion_run,
)

from dataset_provenance import prompt_fingerprint

#: The only questions scored on tool choice alone, and on purpose: a substring
#: cannot score a comparison, since "fakes.py is longer than build_notebook.py"
#: contains every word a right answer would.
COMPARISONS = (
    "Which has more lines, tests/test_config.py or tests/test_sandbox.py?",
    "Which of the two is longer?",
)

QUESTIONS = [question for session in SESSIONS_UNDER_TEST for question in session]
CANONICAL_RUN_MODEFILE = (
    "FROM ./model-f16.gguf\n\n"
    'TEMPLATE """{ if .System }<|im_start|>system\n'
    "{ .System }<|im_end|>\n"
    "{ end }{ if .Prompt }<|im_start|>user\n"
    "{ .Prompt }<|im_end|>\n"
    "{ end }<|im_start|>assistant\n"
    "{ .Response }<|im_end|>\n"
    '"""\n\n'
    "PARAMETER temperature 0.1\n"
    "PARAMETER num_ctx 16384\n"
    'PARAMETER stop "<|im_end|>"\n'
    'PARAMETER stop "Observation:"\n'
)


def test_only_the_comparisons_are_scored_on_tool_choice_alone() -> None:
    unchecked = [q.text for q in QUESTIONS if q.expect is None and not q.unanswerable]

    assert sorted(unchecked) == sorted(COMPARISONS)


def test_a_line_count_is_read_from_the_tree_not_written_down() -> None:
    """So editing a file cannot make the score fall for a reason that is not the model."""
    assert _lines("tests/fakes.py") == str(
        len((Path(__file__).resolve().parent / "fakes.py").read_text(encoding="utf-8").splitlines())
    )


def test_the_last_line_expectation_is_the_file_s_actual_last_line() -> None:
    expected = _last_line("scripts/build_notebook.py")

    assert expected
    assert "\n" not in expected
    assert expected == expected.strip()


def test_every_expectation_is_a_plain_substring() -> None:
    """judge() does a substring match, so an expectation with a comma in it
    can never be met -- commas are stripped from the answer, not from it."""
    assert not any("," in (q.expect or "") for q in QUESTIONS)


def test_promotion_evaluator_returns_live_score_and_writes_report_without_real_ollama(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = tmp_path / "20261112T120000"
    run.mkdir()
    gguf = run / "model-f16.gguf"
    gguf.write_bytes(b"synthetic GGUF")
    (run / "Modelfile").write_text(CANONICAL_RUN_MODEFILE, encoding="utf-8")
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "run": run.name,
                "base_model": "synthetic",
                "examples": 1,
                "strategy": "synthetic",
                "system_prompt_sha256": prompt_fingerprint(),
                "gguf": gguf.name,
                "gguf_sha256": hashlib.sha256(gguf.read_bytes()).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    score = Score(correct=12, checkable=16, asked=19)
    calls: list[list[str]] = []
    promoted: list[tuple[str, Path]] = []
    monkeypatch.setattr("holdout_eval.evaluate", lambda _model: score)
    monkeypatch.setattr(
        "promote_model._ollama_create", lambda tag, model_run: promoted.append((tag, model_run))
    )

    def fake_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr("holdout_eval.subprocess.run", fake_run)
    report_path = tmp_path / "evaluation-report.json"

    assert evaluate_promotion_run(run, report_path) is score
    assert calls[0][:2] == ["ollama", "create"]
    assert calls[0][2] == calls[1][2]
    assert calls[1][:2] == ["ollama", "rm"]
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_id"] == run.name
    assert report["evaluation_id"] == "holdout_eval"
    assert report["score"] == {"correct": 12, "checkable": 16, "error_count": 0}
    assert promoted == []
