"""Tests for the gate between a training run and the tag the demo loads.

Promotion used to be `ollama create omniagent -f Modelfile` typed by hand,
which is how a model nobody had evaluated could end up on the tag the demo is
pinned to. The checks return reasons rather than raising, so a refusal can
print every problem at once instead of the first one.

An empty `checkable` or a non-empty `errors` is a refusal, not a pass: an
evaluation that could not run has not shown anything, and treating silence as
agreement is the mistake `dataset_provenance` was written to stop.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import Score
from promote_model import check_run, check_scores, main

LIVE_PROMPT = "a" * 64


def _run_dir(
    root: Path,
    *,
    system_prompt_sha256: str = LIVE_PROMPT,
    weights: bool = True,
    modelfile: bool = True,
    manifest: bool = True,
) -> Path:
    """A run directory with everything present, spoiling one thing at a time."""
    run = root / "20261011T120000"
    run.mkdir(parents=True, exist_ok=True)
    if manifest:
        (run / "manifest.json").write_text(
            json.dumps(
                {
                    "run": run.name,
                    "base_model": "Qwen/Qwen2.5-1.5B-Instruct",
                    "examples": 153,
                    "strategy": "qlora-4bit",
                    "system_prompt_sha256": system_prompt_sha256,
                    "gguf": "model-f16.gguf",
                }
            )
            + "\n",
            encoding="utf-8",
        )
    if weights:
        (run / "model-f16.gguf").write_bytes(b"GGUF")
    if modelfile:
        (run / "Modelfile").write_text("FROM ./model-f16.gguf\n", encoding="utf-8")
    return run


def _raise(error: Exception) -> Callable[..., NoReturn]:
    def boom(*_args: Any, **_kwargs: Any) -> NoReturn:
        raise error

    return boom


@pytest.fixture(autouse=True)
def _pin_the_live_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tests are about the comparison, not about today's prompt."""
    monkeypatch.setattr("promote_model.prompt_fingerprint", lambda: LIVE_PROMPT)


# --------------------------------------------------------------------------- #
# check_run
# --------------------------------------------------------------------------- #


def test_a_run_whose_prompt_hash_differs_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path, system_prompt_sha256="0" * 64)

    assert "collected under a different system prompt" in " ".join(check_run(run))


def test_a_run_missing_its_weights_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path, weights=False)

    assert any("gguf" in reason for reason in check_run(run))


def test_a_run_missing_its_modelfile_is_refused(tmp_path: Path) -> None:
    """Without it `ollama create` has nothing to read."""
    run = _run_dir(tmp_path, modelfile=False)

    assert any("Modelfile" in reason for reason in check_run(run))


def test_a_run_without_a_manifest_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path, manifest=False)

    assert any("manifest" in reason for reason in check_run(run))


def test_every_problem_is_reported_at_once(tmp_path: Path) -> None:
    """A refusal that names one problem sends the caller round the loop twice."""
    run = _run_dir(tmp_path, weights=False, modelfile=False)

    assert len(check_run(run)) >= 2


def test_a_run_that_passes_everything_has_no_reasons(tmp_path: Path) -> None:
    assert check_run(_run_dir(tmp_path)) == []


# --------------------------------------------------------------------------- #
# check_scores
# --------------------------------------------------------------------------- #


def test_an_evaluation_that_errored_is_not_a_pass() -> None:
    """A score that would otherwise clear the floor, so only `errors` refuses it.

    The first version of this test used correct=0, checkable=0, which the
    checkable guard and the floor both refuse as well -- so removing the
    errors guard left it green. The plan predicted that mutation should turn
    this test red; it did not, because the guards were masking each other.
    """
    scored = {"holdout": Score(correct=12, checkable=16, errors=["connection lost"])}

    assert check_scores(scored, {"correct": 12}) != []


def test_an_evaluation_with_nothing_checkable_is_not_a_pass() -> None:
    """Zero out of zero is silence, and silence is not agreement.

    correct meets the floor here so that only the checkable guard can refuse
    it, for the same reason as the test above.
    """
    scored = {"holdout": Score(correct=12, checkable=0)}

    assert check_scores(scored, {"correct": 12}) != []


def test_a_score_below_the_floor_is_refused() -> None:
    scored = {"holdout": Score(correct=11, checkable=16)}

    assert any("12" in reason for reason in check_scores(scored, {"correct": 12}))


def test_a_score_at_the_floor_passes() -> None:
    scored = {"holdout": Score(correct=12, checkable=16)}

    assert check_scores(scored, {"correct": 12}) == []


def test_no_evaluations_at_all_is_refused() -> None:
    assert check_scores({}, {"correct": 12}) != []


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


def test_a_refused_run_returns_one_and_does_not_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        "promote_model._ollama_create", lambda tag, run: called.append((tag, run))
    )
    run = _run_dir(tmp_path, weights=False)

    assert main([str(run), "--tag", "omniagent"]) == 1
    assert called == []


def test_a_passing_run_is_tagged_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called: list[tuple[str, Path]] = []
    monkeypatch.setattr(
        "promote_model._ollama_create", lambda tag, run: called.append((tag, run))
    )
    run = _run_dir(tmp_path)

    assert main([str(run), "--tag", "omniagent", "--record", str(tmp_path / "promoted.json")]) == 0
    assert called == [("omniagent", run)]
    recorded = json.loads((tmp_path / "promoted.json").read_text("utf-8"))
    assert recorded["tag"] == "omniagent"
    assert recorded["run"] == "20261011T120000"


def test_a_stopped_ollama_fails_loudly_rather_than_tagging_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "promote_model._ollama_create", _raise(OSError("connection refused"))
    )

    with pytest.raises(OSError, match="connection refused"):
        main([str(_run_dir(tmp_path)), "--tag", "omniagent"])
