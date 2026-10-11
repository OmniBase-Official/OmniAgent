"""The directory a training run keeps to itself, and the manifest inside it.

``models/runs/`` was one directory for every run and
``models/<name>-manifest.json`` was one file, so each training overwrote the
record of the one before it. Two fine-tunes exist and that directory looked
empty of history, which is how the problem surfaced.

A run is named for the second it started in, and a second run in the same
second gets a counted suffix rather than quietly landing on top of the first.
The manifest's required fields are enforced rather than documented: a record
that cannot say which base model, how many examples, or which strategy
produced a model is not a record of anything, and that should fail while the
run is still in front of you.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

#: How a run directory is named. Sorts chronologically as a string, which is
#: the only ordering anything reading these directories has.
STAMP_FORMAT = "%Y%m%dT%H%M%S"

#: Without these a manifest cannot answer the question it exists for.
REQUIRED_FIELDS = ("base_model", "examples", "strategy")


def new_run_dir(root: Path, when: datetime) -> Path:
    """Create and return a fresh directory under ``root`` for a run at ``when``.

    Fresh is the point: the suffix counts up rather than reusing a directory
    that already holds someone else's checkpoints.
    """
    stamp = when.strftime(STAMP_FORMAT)
    candidate = root / stamp
    attempt = 1
    while candidate.exists():
        attempt += 1
        candidate = root / f"{stamp}-{attempt}"
    candidate.mkdir(parents=True)
    return candidate


def write_manifest(run: Path, fields: Mapping[str, object]) -> Path:
    """Write ``run/manifest.json``, and say where it went.

    Raises :class:`KeyError` naming every required field the caller left out,
    rather than the first one, so a caller fixing this sees the whole list.
    """
    missing = [field for field in REQUIRED_FIELDS if field not in fields]
    if missing:
        raise KeyError(
            f"manifest for {run.name} is missing {', '.join(missing)}: a record that "
            "cannot say what produced the model is not a record"
        )

    # The run name travels inside the file, because this manifest is also
    # copied to a flat path for older readers and there it has nothing else to
    # say which run it came from.
    payload = {"run": run.name, **dict(fields)}
    path = run / "manifest.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
