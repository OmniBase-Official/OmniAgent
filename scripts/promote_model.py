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
import json
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


def _ollama_create(tag: str, run: Path) -> None:
    """Register the run's model under ``tag``, beside its own Modelfile.

    `cwd` is the run directory because the Modelfile's FROM is relative.
    """
    subprocess.run(  # noqa: S603 - fixed argv, no shell
        ["ollama", "create", tag, "-f", "Modelfile"],  # noqa: S607
        cwd=run,
        check=True,
    )


def check_run(run: Path) -> list[str]:
    """Every reason ``run`` may not be promoted. Empty means it may."""
    reasons: list[str] = []

    manifest_path = run / "manifest.json"
    if not manifest_path.is_file():
        # Without it nothing below can be checked, so say so and stop.
        return [f"{run.name} has no manifest.json, so nothing about it can be checked"]

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{manifest_path.name} is not valid JSON: {exc}"]

    recorded = manifest.get("system_prompt_sha256")
    live = prompt_fingerprint()
    if recorded != live:
        reasons.append(
            f"{run.name} was collected under a different system prompt "
            f"({str(recorded)[:12]} against {live[:12]}), so it is not trained for "
            "the prompt it would be served"
        )

    weights = manifest.get("gguf")
    if not weights:
        reasons.append(f"{manifest_path.name} does not name a gguf")
    elif not (run / str(weights)).is_file():
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
        "--record", type=Path, default=RECORD, help="Where to record the promotion."
    )
    args = parser.parse_args(argv)

    # No scores are passed in yet: an evaluation harness calls check_scores
    # directly. Promoting without one is refused by check_scores({}).
    reasons = check_run(args.run)
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
