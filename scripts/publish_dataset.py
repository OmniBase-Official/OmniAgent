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
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from dataset_provenance import sidecar_path

#: The checksum file, in the format `sha256sum` itself writes and reads.
SUMS_NAME = "SHA256SUMS"
MANIFEST_NAME = "MANIFEST.json"

#: Files that describe the publish rather than belong to it, so they are not
#: listed inside the checksum file they would have to hash themselves.
SELF_DESCRIBING = frozenset({SUMS_NAME, MANIFEST_NAME})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")

#: Keep verification bounded even when a removable destination is corrupted.
MAX_SUMS_BYTES = 16 * 1024 * 1024
MAX_SUMS_LINE_BYTES = 4 * 1024
MAX_SUMS_ENTRIES = 100_000


class PublishError(RuntimeError):
    """A dataset that cannot be published, or did not arrive intact."""


def _is_reparse_point(path: Path) -> bool:
    """Recognize symlinks and platform reparse points without following them."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(flag and attributes & flag)


def _destination_root(dest: Path, *, create: bool) -> Path:
    """Reject symlink/reparse path components before using a bundle directory."""
    absolute = dest.expanduser().absolute()
    for component in (absolute, *absolute.parents):
        if _is_reparse_point(component):
            raise PublishError(f"destination path contains a symlink or reparse point: {component}")
    if create:
        absolute.mkdir(parents=True, exist_ok=True)
    if not absolute.is_dir():
        raise PublishError(f"destination is not a directory: {absolute}")
    resolved = absolute.resolve(strict=True)
    if any(_is_reparse_point(component) for component in (absolute, *absolute.parents)):
        raise PublishError("destination path changed to a symlink or reparse point")
    return resolved


def _check_destination_file(path: Path, dest_root: Path) -> None:
    """Allow normal overwrite of an in-bundle regular file, reject redirects."""
    if _is_reparse_point(path):
        raise PublishError(f"destination entry is a symlink or reparse point: {path.name}")
    if not path.exists():
        return
    try:
        resolved = path.resolve(strict=True)
        metadata = path.lstat()
    except OSError as exc:
        raise PublishError(f"destination entry cannot be inspected: {path.name}") from exc
    if not resolved.is_relative_to(dest_root):
        raise PublishError(f"destination entry resolves outside the bundle: {path.name}")
    if not stat.S_ISREG(metadata.st_mode):
        raise PublishError(f"destination entry is not a regular file: {path.name}")
    if metadata.st_nlink != 1:
        raise PublishError(f"destination entry is hard-linked outside its own name: {path.name}")


def _safe_bundle_name(name: str) -> bool:
    """Accept only one filename, with no POSIX or Windows path syntax."""
    return bool(
        name
        and name not in {".", ".."}
        and "\x00" not in name
        and ":" not in name
        and "/" not in name
        and "\\" not in name
        and not PurePosixPath(name).is_absolute()
        and not PureWindowsPath(name).is_absolute()
        and not PureWindowsPath(name).drive
        and PureWindowsPath(name).name == name
    )


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

    dest_root = _destination_root(dest, create=True)
    output_names = {source.name for source in sources} | {SUMS_NAME, MANIFEST_NAME}
    for name in output_names:
        if not _safe_bundle_name(name):
            raise PublishError(f"not a safe destination filename: {name!r}")
        _check_destination_file(dest_root / name, dest_root)

    expected: dict[str, str] = {}
    for source in sources:
        target = dest_root / source.name
        _check_destination_file(target, dest_root)
        shutil.copy2(source, target)
        expected[source.name] = digest(source)

    arrived = {name: digest(dest_root / name) for name in expected}
    corrupted = sorted(name for name, value in expected.items() if arrived[name] != value)
    if corrupted:
        raise PublishError(f"copied but does not match the source: {', '.join(corrupted)}")

    sums_path = dest_root / SUMS_NAME
    _check_destination_file(sums_path, dest_root)
    sums_path.write_text(
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
    manifest_path = dest_root / MANIFEST_NAME
    _check_destination_file(manifest_path, dest_root)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _iter_sums_lines(sums: Path) -> Iterator[str]:
    """Stream bounded checksum lines, refusing malformed encodings or excess work."""
    try:
        sums_size = sums.stat().st_size
    except OSError as exc:
        raise PublishError(f"could not inspect {SUMS_NAME}") from exc
    if sums_size > MAX_SUMS_BYTES:
        raise PublishError(f"{SUMS_NAME} exceeds the {MAX_SUMS_BYTES}-byte verification limit")

    bytes_seen = 0
    entries_seen = 0
    try:
        with sums.open("rb") as handle:
            while raw := handle.readline(MAX_SUMS_LINE_BYTES + 1):
                bytes_seen += len(raw)
                if bytes_seen > MAX_SUMS_BYTES:
                    raise PublishError(
                        f"{SUMS_NAME} exceeded the {MAX_SUMS_BYTES}-byte verification limit"
                    )
                if len(raw) > MAX_SUMS_LINE_BYTES:
                    raise PublishError(
                        f"{SUMS_NAME} has a line over the "
                        f"{MAX_SUMS_LINE_BYTES}-byte verification limit"
                    )
                entries_seen += 1
                if entries_seen > MAX_SUMS_ENTRIES:
                    raise PublishError(
                        f"{SUMS_NAME} exceeds the {MAX_SUMS_ENTRIES}-entry verification limit"
                    )
                try:
                    line = raw.decode("utf-8").rstrip("\r\n")
                except UnicodeDecodeError as exc:
                    raise PublishError(f"{SUMS_NAME} is not valid UTF-8") from exc
                yield line
    except OSError as exc:
        raise PublishError(f"could not read {SUMS_NAME}") from exc


def _parse_sums_line(line: str) -> tuple[str, str] | None:
    """Return checksum and safe basename, or None for an invalid record."""
    value, separator, name = line.partition("  ")
    if not separator or not _SHA256_PATTERN.fullmatch(value) or not _safe_bundle_name(name):
        return None
    return value, name


def _verify_sums_entry(dest_root: Path, value: str, name: str) -> bool:
    """Check one entry without following links or leaving the bundle."""
    path = dest_root / name
    if _is_reparse_point(path) or not path.is_file():
        return False
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(dest_root) or not stat.S_ISREG(path.stat().st_mode):
            return False
        return digest(resolved) == value
    except OSError:
        return False


def verify(dest: Path) -> list[str]:
    """Names of published files that are missing or no longer match, sorted.

    An empty list is the only passing answer. Run it after the drive has been
    unplugged and brought back, which is the case a copy command cannot cover.
    """
    dest_root = _destination_root(dest, create=False)
    sums = dest_root / SUMS_NAME
    if _is_reparse_point(sums):
        raise PublishError(f"{SUMS_NAME} must not be a symlink or reparse point")
    if not sums.is_file():
        raise PublishError(f"nothing published here: no {SUMS_NAME} in {dest}")

    broken: list[str] = []
    for line in _iter_sums_lines(sums):
        if not line.strip():
            continue
        parsed = _parse_sums_line(line)
        if parsed is None:
            _, _, name = line.partition("  ")
            broken.append(name or "[invalid SHA256SUMS entry]")
            continue
        value, name = parsed
        if not _verify_sums_entry(dest_root, value, name):
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
