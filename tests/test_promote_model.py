"""Tests for the live-evaluation gate between a run and its promoted tag."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from eval_scoring import Score
from promote_model import (
    check_run,
    check_scores,
    main,
    verified_run_gguf,
    verified_run_modelfile,
)

LIVE_PROMPT = "a" * 64
CANONICAL_TEMPLATE = (
    'TEMPLATE """{ if .System }<|im_start|>system\n'
    "{ .System }<|im_end|>\n"
    "{ end }{ if .Prompt }<|im_start|>user\n"
    "{ .Prompt }<|im_end|>\n"
    "{ end }<|im_start|>assistant\n"
    "{ .Response }<|im_end|>\n"
    '"""'
)


def _canonical_modelfile(gguf_name: str) -> str:
    return (
        f"FROM ./{gguf_name}\n\n{CANONICAL_TEMPLATE}\n\n"
        'PARAMETER temperature 0.1\n'
        "PARAMETER num_ctx 16384\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "Observation:"\n'
    )


def _run_dir(root: Path, *, system_prompt_sha256: str = LIVE_PROMPT) -> Path:
    run = root / "20261011T120000"
    run.mkdir(parents=True, exist_ok=True)
    gguf = b"GGUF"
    (run / "manifest.json").write_text(
        json.dumps(
            {
                "run": run.name,
                "base_model": "synthetic",
                "examples": 1,
                "strategy": "synthetic",
                "system_prompt_sha256": system_prompt_sha256,
                "gguf": "model-f16.gguf",
                "gguf_sha256": hashlib.sha256(gguf).hexdigest(),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run / "model-f16.gguf").write_bytes(gguf)
    (run / "Modelfile").write_text(
        _canonical_modelfile("model-f16.gguf"), encoding="utf-8"
    )
    return run


@pytest.fixture(autouse=True)
def _pin_the_live_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("promote_model.prompt_fingerprint", lambda: LIVE_PROMPT)


def test_run_with_different_prompt_hash_is_refused(tmp_path: Path) -> None:
    assert "collected under a different system prompt" in " ".join(
        check_run(_run_dir(tmp_path, system_prompt_sha256="0" * 64))
    )


def test_valid_run_has_no_preflight_reasons(tmp_path: Path) -> None:
    assert check_run(_run_dir(tmp_path)) == []


@pytest.mark.parametrize(
    "directive",
    [
        'SYSTEM "attacker-controlled system prompt"',
        'TEMPLATE """attacker-controlled template"""',
        "ADAPTER ./attacker-adapter.gguf",
        "PARAMETER temperature 0.9",
    ],
)
def test_modelfile_rejects_extra_ollama_directives(
    tmp_path: Path, directive: str
) -> None:
    run = _run_dir(tmp_path)
    modelfile = run / "Modelfile"
    modelfile.write_text(
        modelfile.read_text(encoding="utf-8") + directive + "\n",
        encoding="utf-8",
    )

    _, error = verified_run_modelfile(run)

    assert error is not None
    assert "canonical generated directives" in error


def test_modelfile_symlink_escape_is_refused(tmp_path: Path) -> None:
    run = _run_dir(tmp_path)
    outside_modelfile = tmp_path / "outside-Modelfile"
    outside_modelfile.write_text(
        _canonical_modelfile("model-f16.gguf"), encoding="utf-8"
    )
    (run / "Modelfile").unlink()
    try:
        (run / "Modelfile").symlink_to(outside_modelfile)
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable on this system: {exc}")

    _, error = verified_run_modelfile(run)

    assert error == "the run Modelfile must not be a symlink"


@pytest.mark.parametrize("gguf_name", ["../outside.gguf", "sub/model.gguf", "..\\outside.gguf"])
def test_manifest_gguf_must_be_a_safe_generated_basename(
    tmp_path: Path, gguf_name: str
) -> None:
    run = _run_dir(tmp_path)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["gguf"] = gguf_name
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    path, digest, error = verified_run_gguf(run)

    assert path is None
    assert digest is None
    assert error == "the run manifest does not name a gguf artifact"


def test_evaluation_errors_refuse_score() -> None:
    assert check_scores(
        {"holdout": Score(correct=12, checkable=16, errors=["failed"])},
        {"correct": 12},
    )


def test_empty_evaluation_refuses_score() -> None:
    assert check_scores({}, {"correct": 12})


def test_zero_checkable_refuses_score() -> None:
    assert check_scores({"holdout": Score(correct=12)}, {"correct": 12})


def test_below_floor_refuses_score() -> None:
    assert check_scores({"holdout": Score(correct=11, checkable=16)}, {"correct": 12})


def test_at_floor_passes_score() -> None:
    assert check_scores({"holdout": Score(correct=12, checkable=16)}, {"correct": 12}) == []


@pytest.mark.parametrize(
    "score",
    [
        pytest.param(Score(correct=11, checkable=16), id="below-floor"),
        pytest.param(Score(correct=12, checkable=0), id="no-checkable-answers"),
        pytest.param(Score(correct=12, checkable=16, errors=["failed"]), id="evaluation-error"),
    ],
)
def test_live_evaluation_refusal_never_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, score: Score
) -> None:
    run = _run_dir(tmp_path)
    calls: list[tuple[str, Path]] = []
    monkeypatch.setattr("holdout_eval.evaluate_promotion_run", lambda *_args: score)
    monkeypatch.setattr(
        "promote_model._ollama_create", lambda tag, path: calls.append((tag, path))
    )

    assert main([str(run), "--tag", "omniagent", "--record", str(tmp_path / "record.json")]) == 1
    assert calls == []
    assert not (tmp_path / "record.json").exists()


def test_only_qualifying_live_evaluator_score_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run_dir(tmp_path)
    score = Score(correct=12, checkable=16)
    evaluation_calls: list[Path] = []
    promotion_calls: list[tuple[str, Path]] = []

    def fake_evaluate(evaluated_run: Path, _report: Path | None = None) -> Score:
        evaluation_calls.append(evaluated_run)
        return score

    monkeypatch.setattr(
        "holdout_eval.evaluate_promotion_run", fake_evaluate
    )
    monkeypatch.setattr(
        "promote_model._ollama_create",
        lambda tag, path: promotion_calls.append((tag, path)),
    )

    assert main(
        [str(run), "--tag", "omniagent", "--record", str(tmp_path / "record.json")]
    ) == 0
    assert evaluation_calls == [run]
    assert promotion_calls == [("omniagent", run)]
    record = json.loads((tmp_path / "record.json").read_text(encoding="utf-8"))
    assert record["run"] == run.name


def test_evaluation_exception_refuses_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _run_dir(tmp_path)
    promoted: list[Path] = []

    def fail(*_args: object) -> Score:
        raise RuntimeError("private evaluation detail")

    monkeypatch.setattr("holdout_eval.evaluate_promotion_run", fail)
    monkeypatch.setattr("promote_model._ollama_create", lambda _tag, path: promoted.append(path))

    assert main([str(run), "--tag", "omniagent", "--record", str(tmp_path / "record.json")]) == 1
    assert promoted == []
    assert "private evaluation detail" not in capsys.readouterr().err
    assert not (tmp_path / "record.json").exists()


def test_failed_temporary_tag_cleanup_refuses_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _run_dir(tmp_path)
    commands: list[list[str]] = []
    promoted: list[Path] = []

    def fake_run(argv: list[str], **_kwargs: object) -> object:
        commands.append(argv)
        if argv[1] == "rm":
            raise OSError("cleanup detail")
        return object()

    monkeypatch.setattr("holdout_eval.evaluate", lambda _tag: Score(correct=16, checkable=16))
    monkeypatch.setattr("holdout_eval.subprocess.run", fake_run)
    monkeypatch.setattr(
        "holdout_eval.verified_run_gguf",
        lambda path: (path / "model-f16.gguf", "a" * 64, None),
    )
    monkeypatch.setattr(
        "promote_model.verified_run_gguf",
        lambda path: (path / "model-f16.gguf", "a" * 64, None),
    )
    monkeypatch.setattr("holdout_eval.verified_run_modelfile", lambda _path: ("b" * 64, None))
    monkeypatch.setattr("promote_model.verified_run_modelfile", lambda _path: ("b" * 64, None))
    monkeypatch.setattr("promote_model._ollama_create", lambda _tag, path: promoted.append(path))

    assert main([str(run), "--tag", "omniagent", "--record", str(tmp_path / "record.json")]) == 1
    assert [command[1] for command in commands] == ["create", "rm"]
    assert promoted == []
    assert "temporary evaluation tag cleanup failed" in capsys.readouterr().err
    assert not (tmp_path / "record.json").exists()


def test_optional_evaluation_report_is_not_a_promotion_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = _run_dir(tmp_path)
    monkeypatch.setattr("holdout_eval.evaluate_promotion_run", lambda *_args: Score(12, 16))
    monkeypatch.setattr("promote_model._ollama_create", lambda *_args: None)
    report = tmp_path / "report.json"

    assert main(
        [
            str(run),
            "--tag",
            "omniagent",
            "--evaluation-report",
            str(report),
            "--record",
            str(tmp_path / "record.json"),
        ]
    ) == 0
    assert not report.exists()
