"""The gate between a training run and the tag the agent loads.

Promotion used to be ``ollama create omniagent -f Modelfile`` typed by hand,
which is how a model nobody had evaluated could land on the tag the demo is
pinned to. On 2026-10-07 that nearly happened: the notebook's defaults would
have overwritten both the files and the tag of a model rehearsed at 30/30,
three days before a demo.

Both checks return **reasons** rather than raising, so a refusal prints every
problem at once instead of sending the caller round the loop one fix at a
time.

Two refusals are worth stating because they are easy to write the other way
round. An evaluation with nothing ``checkable`` is silence, not agreement --
zero out of zero has shown nothing. And an evaluation carrying ``errors`` has
not finished, so its score describes a partial run; `dataset_provenance`
exists because this project has read silence as agreement before.

The connection error from a stopped Ollama is deliberately not caught: a
promotion that quietly tagged nothing would be worse than one that stops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from eval_scoring import Score

from dataset_provenance import prompt_fingerprint

#: Where a promotion is recorded, so the tag can say which run it came from.
RECORD = PROJECT / "models" / "promoted.json"

#: The scores a run has to reach. Deliberately not a default in `main`: a
#: floor that nobody chose is a floor nobody believes.
DEFAULT_FLOOR: Mapping[str, int] = {"correct": 12}
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_GGUF_BASENAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.gguf\Z")
_EXPECTED_TEMPLATE = (
    'TEMPLATE """{ if .System }<|im_start|>system\n'
    "{ .System }<|im_end|>\n"
    "{ end }{ if .Prompt }<|im_start|>user\n"
    "{ .Prompt }<|im_end|>\n"
    "{ end }<|im_start|>assistant\n"
    "{ .Response }<|im_end|>\n"
    '"""'
)


class PromotionEvaluationError(RuntimeError):
    """A fixed, safe-to-display reason a holdout run cannot authorize promotion."""


def _ollama_create(tag: str, run: Path) -> None:
    """Register the run's model under ``tag``, beside its own Modelfile.

    `cwd` is the run directory because the Modelfile's FROM is relative.
    """
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["ollama", "create", tag, "-f", "Modelfile"],  # noqa: S607
        cwd=run,
        check=True,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def verified_run_gguf(run: Path) -> tuple[Path | None, str | None, str | None]:
    """Return the in-run GGUF and verified digest, or a fixed refusal reason."""
    try:
        manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, None, "the run manifest cannot bind evaluation to a GGUF"
    if not isinstance(manifest, dict):
        return None, None, "the run manifest cannot bind evaluation to a GGUF"
    gguf_name = manifest.get("gguf")
    if (
        not isinstance(gguf_name, str)
        or not _GGUF_BASENAME_PATTERN.fullmatch(gguf_name)
        or Path(gguf_name).name != gguf_name
    ):
        return None, None, "the run manifest does not name a gguf artifact"
    try:
        resolved_run = run.resolve(strict=True)
        resolved_gguf = (resolved_run / gguf_name).resolve(strict=True)
        if not resolved_gguf.is_relative_to(resolved_run) or not resolved_gguf.is_file():
            return None, None, "the run gguf path is not a file inside the run directory"
        actual_sha256 = _sha256_file(resolved_gguf)
    except (OSError, RuntimeError):
        return None, None, "the run gguf artifact cannot be verified"
    recorded_sha256 = manifest.get("gguf_sha256")
    if (
        not isinstance(recorded_sha256, str)
        or not _SHA256_PATTERN.fullmatch(recorded_sha256)
        or recorded_sha256 != actual_sha256
    ):
        return None, None, "the run manifest gguf checksum does not match the artifact"
    return resolved_gguf, actual_sha256, None


def verified_run_modelfile(run: Path) -> tuple[str | None, str | None]:
    """Verify the canonical generated Modelfile and hash its exact contents."""
    gguf_path, _, artifact_error = verified_run_gguf(run)
    if artifact_error or gguf_path is None:
        return None, artifact_error or "the run gguf cannot be verified"
    try:
        resolved_run = run.resolve(strict=True)
        modelfile_path = run / "Modelfile"
        if modelfile_path.is_symlink():
            return None, "the run Modelfile must not be a symlink"
        resolved_modelfile = modelfile_path.resolve(strict=True)
        if (
            not resolved_modelfile.is_relative_to(resolved_run)
            or not stat.S_ISREG(resolved_modelfile.stat().st_mode)
        ):
            return None, "the run Modelfile must be a regular file inside the run directory"
        modelfile_bytes = resolved_modelfile.read_bytes()
        modelfile_text = modelfile_bytes.decode("utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError, RuntimeError):
        return None, "the run Modelfile cannot be verified"
    expected = (
        f"FROM ./{gguf_path.name}\n\n{_EXPECTED_TEMPLATE}\n\n"
        'PARAMETER temperature 0.1\n'
        "PARAMETER num_ctx 16384\n"
        'PARAMETER stop "<|im_end|>"\n'
        'PARAMETER stop "Observation:"\n'
    )
    if "\r" in modelfile_text or modelfile_text != expected:
        return None, "the run Modelfile does not match the canonical generated directives"
    return hashlib.sha256(modelfile_bytes).hexdigest(), None


def write_evaluation_report(path: Path, run: Path, score: Score) -> None:
    """Write sanitized report output; this file is never promotion authority."""
    payload = {
        "evaluation_id": "holdout_eval",
        "run_id": run.name,
        "asked": score.asked,
        "score": {
            "correct": score.correct,
            "checkable": score.checkable,
            "error_count": len(score.errors),
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def check_run(run: Path) -> list[str]:
    """Every reason ``run`` may not be promoted. Empty means it may."""
    reasons: list[str] = []

    manifest_path = run / "manifest.json"
    if not manifest_path.is_file():
        # Without it nothing below can be checked, so say so and stop.
        return [f"{run.name} has no manifest.json, so nothing about it can be checked"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [f"{manifest_path.name} is unreadable or is not valid JSON"]
    if not isinstance(manifest, dict):
        return [f"{manifest_path.name} must contain a JSON object"]
    if manifest.get("run") != run.name:
        return [f"{manifest_path.name} identifies a different run"]

    recorded = manifest.get("system_prompt_sha256")
    live = prompt_fingerprint()
    if recorded != live:
        reasons.append(
            f"{run.name} was collected under a different system prompt "
            f"({str(recorded)[:12]} against {live[:12]}), so it is not trained for "
            "the prompt it would be served"
        )

    weights = manifest.get("gguf")
    if not isinstance(weights, str) or not weights:
        reasons.append(f"{manifest_path.name} does not name a gguf")
    elif not (run / weights).is_file():
        reasons.append(f"the gguf it names is missing: {weights}")

    if not (run / "Modelfile").is_file():
        reasons.append(f"{run.name} has no Modelfile, so ollama create has nothing to read")

    return reasons


def check_scores(scores: Mapping[str, Score], floor: Mapping[str, int]) -> list[str]:
    """Every reason the measured scores do not clear ``floor``."""
    if not scores:
        return ["no evaluation was run, and an unmeasured model is not a promoted one"]

    reasons: list[str] = []
    for name, score in scores.items():
        if score.errors:
            reasons.append(
                f"{name} did not finish ({len(score.errors)} error(s), first: "
                f"{score.errors[0]}), so its score describes a partial run"
            )
            continue
        if score.checkable == 0:
            reasons.append(f"{name} had nothing checkable, which is silence rather than a pass")
            continue
        for field, minimum in floor.items():
            actual = getattr(score, field, None)
            if actual is None:
                reasons.append(f"{name} does not report {field}")
            elif actual < minimum:
                reasons.append(
                    f"{name} {field} is {actual}/{score.checkable}, below the floor of {minimum}"
                )
    return reasons


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Promote a training run to an Ollama tag, if the checks allow it."
    )
    parser.add_argument("run", type=Path, help="The run directory under models/runs/.")
    parser.add_argument("--tag", required=True, help="Ollama tag to register it as.")
    parser.add_argument(
        "--evaluation-report",
        type=Path,
        help="Optional sanitized report path; reports are never used to authorize promotion.",
    )
    parser.add_argument(
        "--record", type=Path, default=RECORD, help="Where to record the promotion."
    )
    args = parser.parse_args(argv)

    reasons = check_run(args.run)
    if reasons:
        print(f"[!] {args.run} is not promotable:", file=sys.stderr)
        for reason in reasons:
            print(f"    - {reason}", file=sys.stderr)
        return 1

    try:
        # Import lazily to avoid a module cycle: holdout_eval uses check_run
        # and artifact validation from this module during its preflight.
        from holdout_eval import evaluate_promotion_run

        score = evaluate_promotion_run(args.run, args.evaluation_report)
    except PromotionEvaluationError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - unexpected evaluator failures must refuse promotion
        print(
            f"[!] holdout evaluation failed ({type(exc).__name__}); promotion is refused",
            file=sys.stderr,
        )
        return 1

    reasons = check_scores({"holdout_eval": score}, DEFAULT_FLOOR)
    if reasons:
        print(f"[!] {args.run} is not promotable:", file=sys.stderr)
        for reason in reasons:
            print(f"    - {reason}", file=sys.stderr)
        return 1

    _ollama_create(args.tag, args.run)

    args.record.parent.mkdir(parents=True, exist_ok=True)
    args.record.write_text(
        json.dumps(
            {
                "tag": args.tag,
                "run": args.run.name,
                "promoted_at": datetime.now(UTC).isoformat(timespec="seconds"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"promoted {args.run.name} as {args.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
