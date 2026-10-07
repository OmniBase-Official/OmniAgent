"""Put a dataset somewhere it can be trained from, and prove what arrived.

Not a copy command, for two reasons measured rather than assumed.

The destination is a removable exFAT volume. A dataset is only worth training
on if what arrived is what was collected, so every file is hashed at the
source, hashed again at the destination, and the publish fails if the two
disagree. ``verify`` re-checks later, when the drive has been unplugged and
brought back.

And provenance cannot be allowed to go missing. ``dataset_provenance`` records
the system prompt a dataset was collected under and refuses to read a missing
sidecar as agreement. It records nothing else, though -- and two other things
change the data just as much:

- **which teacher produced the trajectories.** The bank is asked of whatever
  model is configured; a 1.5B fine-tune and a 7B coder do not answer alike.
- **which workspace rule the agent ran under.** Until 2026-10-06 the agent
  could read its own earlier transcripts while being asked the bank, so a
  trajectory could contain an answer copied out of a log. Sealed, it cannot.
  A dataset collected on either side of that is a different dataset.

So ``MANIFEST.json`` records both beside the sidecar's fingerprint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from dataset_provenance import sidecar_path

#: The checksum file, in the format `sha256sum` itself writes and reads.
SUMS_NAME = "SHA256SUMS"
MANIFEST_NAME = "MANIFEST.json"

#: Files that describe the publish rather than belong to it, so they are not
#: listed inside the checksum file they would have to hash themselves.
SELF_DESCRIBING = frozenset({SUMS_NAME, MANIFEST_NAME})


class PublishError(RuntimeError):
    """A dataset that cannot be published, or did not arrive intact."""


def digest(path: Path) -> str:
    """The sha256 of a file, read in chunks so a large log does not load whole."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _head_commit() -> str | None:
    """The source commit, or None outside a checkout."""
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            ["git", "-C", str(PROJECT), "rev-parse", "--short", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git here
        return None
    return result.stdout.strip() or None


def publish(  # noqa: PLR0913 - each argument is a separate fact the manifest has to record
    dataset: Path,
    dest: Path,
    *,
    teacher: str,
    workspace_rule: str | None = None,
    extras: Iterable[Path] = (),
    source_commit: str | None = None,
) -> dict[str, object]:
    """Copy ``dataset``, its sidecar and ``extras`` into ``dest``, and prove it.

    Returns the manifest, which is also written into ``dest``. Raises
    :class:`PublishError` if the sidecar is missing or if any file fails to
    match its source digest after the copy.
    """
    sidecar = sidecar_path(dataset)
    if not sidecar.is_file():
        raise PublishError(
            f"no provenance sidecar for {dataset.name}: expected {sidecar.name}. "
            "Run dataset_provenance.write_sidecar first -- a dataset that cannot "
            "say what prompt it was collected under has not been shown to match it."
        )

    sources = [dataset, sidecar, *extras]
    missing = [str(path) for path in sources if not path.is_file()]
    if missing:
        raise PublishError(f"not a file: {', '.join(missing)}")

    dest.mkdir(parents=True, exist_ok=True)
    expected: dict[str, str] = {}
    for source in sources:
        shutil.copy2(source, dest / source.name)
        expected[source.name] = digest(source)

    arrived = {name: digest(dest / name) for name in expected}
    corrupted = sorted(name for name, value in expected.items() if arrived[name] != value)
    if corrupted:
        raise PublishError(f"copied but does not match the source: {', '.join(corrupted)}")

    (dest / SUMS_NAME).write_text(
        "".join(f"{value}  {name}\n" for name, value in sorted(expected.items())),
        encoding="utf-8",
    )

    recorded = json.loads(sidecar.read_text(encoding="utf-8"))
    manifest: dict[str, object] = {
        "dataset": dataset.name,
        "examples": recorded.get("examples"),
        "system_prompt_sha256": recorded.get("system_prompt_sha256"),
        "teacher_model": teacher,
        "workspace_rule": workspace_rule,
        "source_commit": source_commit if source_commit is not None else _head_commit(),
        "published_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": dict(sorted(expected.items())),
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(dest: Path) -> list[str]:
    """Names of published files that are missing or no longer match, sorted.

    An empty list is the only passing answer. Run it after the drive has been
    unplugged and brought back, which is the case a copy command cannot cover.
    """
    sums = dest / SUMS_NAME
    if not sums.is_file():
        raise PublishError(f"nothing published here: no {SUMS_NAME} in {dest}")

    broken: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value, _, name = line.partition("  ")
        path = dest / name
        if not path.is_file() or digest(path) != value:
            broken.append(name)
    return sorted(broken)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish a dataset and its provenance to a training store."
    )
    # dataset and --teacher are optional only because --verify-only reads
    # SHA256SUMS and nothing else; requiring them there made the documented
    # re-check command ask for a teacher it ignores. Still required to publish.
    parser.add_argument(
        "dataset", type=Path, nargs="?", help="The exported .jsonl dataset."
    )
    parser.add_argument("--dest", type=Path, required=True, help="Destination directory.")
    parser.add_argument("--teacher", help="Model tag the bank was asked of.")
    parser.add_argument(
        "--workspace-rule",
        help="How the agent's workspace was restricted while collecting.",
    )
    parser.add_argument(
        "--also", type=Path, nargs="*", default=(), help="Extra files to publish alongside."
    )
    parser.add_argument(
        "--verify-only", action="store_true", help="Re-check an existing destination."
    )
    args = parser.parse_args(argv)

    if not args.verify_only and (args.dataset is None or args.teacher is None):
        parser.error("dataset and --teacher are required unless --verify-only is given")

    try:
        if args.verify_only:
            broken = verify(args.dest)
            print(f"[!] {len(broken)} file(s) bad: {', '.join(broken)}" if broken else "verified")
            return 1 if broken else 0
        manifest = publish(
            args.dataset,
            args.dest,
            teacher=args.teacher,
            workspace_rule=args.workspace_rule,
            extras=tuple(args.also),
        )
    except PublishError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    published = manifest["files"]
    if not isinstance(published, dict):  # pragma: no cover - publish always sets it
        return 1
    print(f"published {len(published)} file(s) to {args.dest}")
    for name, value in sorted(published.items()):
        print(f"  {str(value)[:12]}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
