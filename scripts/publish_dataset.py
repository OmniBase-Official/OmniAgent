"""Put a dataset somewhere it can be trained from, and prove what arrived.

Not a copy command, for two reasons measured rather than assumed.

The destination may be removable media. A dataset is only worth training on
if what arrived is what was collected, so every file is hashed from its pinned
source handle, hashed again through the staging handle, and the publish fails
if the two disagree. ``verify`` re-checks later, when the drive has been
unplugged and brought back. Publishing fails closed when the filesystem cannot
enforce private staging.

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
import errno
import hashlib
import io
import json
import re
import secrets
import stat
import subprocess
import sys
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import SimpleNamespace
from typing import cast

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import dataset_provenance
import validate_dataset
from dataset_provenance import ProvenanceError, dataset_fingerprint, read_sidecar, sidecar_path
from publisher_root import PublisherRoot
from securefs import SecureRoot
from validate_dataset import validate_file

__all__ = ["SecureRoot"]

#: The checksum file, in the format `sha256sum` itself writes and reads.
SUMS_NAME = "SHA256SUMS"
MANIFEST_NAME = "MANIFEST.json"

#: Files that describe the publish rather than belong to it, so they are not
#: listed inside the checksum file they would have to hash themselves.
SELF_DESCRIBING = frozenset({SUMS_NAME, MANIFEST_NAME})
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{7,64}\Z")
_WINDOWS_RESERVED_DEVICE_NAMES = {
    "aux",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
    *(f"com{number}" for number in "¹²³"),
    *(f"lpt{number}" for number in "¹²³"),
}

#: Keep verification bounded even when a removable destination is corrupted.
MAX_SUMS_BYTES = 16 * 1024 * 1024
MAX_SUMS_LINE_BYTES = 4 * 1024
MAX_SUMS_ENTRIES = 100_000
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_TEACHER_MODEL_BYTES = 256
MAX_WORKSPACE_RULE_BYTES = 1024
_STAGING_PREFIX = ".omniagent-publish-"


class PublishError(RuntimeError):
    """A dataset that cannot be published, or did not arrive intact."""


def _metadata_text_within_limit(value: object, limit: int, *, optional: bool = False) -> bool:
    if optional and value is None:
        return True
    if not isinstance(value, str) or any(not character.isprintable() for character in value):
        return False
    try:
        return len(value.encode("utf-8")) <= limit
    except UnicodeEncodeError:
        return False


def _validate_publish_metadata(teacher: object, workspace_rule: object) -> None:
    if (
        not isinstance(teacher, str)
        or not teacher.strip()
        or not _metadata_text_within_limit(teacher, MAX_TEACHER_MODEL_BYTES)
    ):
        raise PublishError(
            "teacher metadata must be printable text of at most "
            f"{MAX_TEACHER_MODEL_BYTES} UTF-8 bytes"
        )
    if not _metadata_text_within_limit(workspace_rule, MAX_WORKSPACE_RULE_BYTES, optional=True):
        raise PublishError(
            "workspace rule metadata must be printable text of at most "
            f"{MAX_WORKSPACE_RULE_BYTES} UTF-8 bytes"
        )


class _SnapshotPath:
    """A minimal Path-like view over immutable bytes captured from one handle."""

    def __init__(self, name: str, snapshots: dict[str, bytes]) -> None:
        self.name = name
        self._snapshots = snapshots

    def with_name(self, name: str) -> _SnapshotPath:
        return _SnapshotPath(name, self._snapshots)

    def is_file(self) -> bool:
        return self.name in self._snapshots

    def stat(self) -> SimpleNamespace:
        return SimpleNamespace(
            st_mode=stat.S_IFREG | 0o600, st_size=len(self._snapshots[self.name]), st_nlink=1
        )

    def lstat(self) -> SimpleNamespace:
        return self.stat()

    def open(self, mode: str = "rb") -> io.BytesIO:
        if mode != "rb":
            raise ValueError("snapshots are read-only")
        return io.BytesIO(self._snapshots[self.name])

    def __str__(self) -> str:
        return self.name


class _OpenedSource:
    """A source object pinned by its parent handle and opened exactly once."""

    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().absolute()
        self.root = SecureRoot(self.path.parent)
        self.handle: int | None = None
        try:
            self.handle = self.root.open(self.path.name, immutable=True)
            self.size, _links, is_dir = self.root.info(self.handle)
            if is_dir:
                raise PublishError(f"not a file: {self.path}")  # noqa: TRY301 - close handle on failure
            if not self.root.immutable_to_other_users(self.handle):
                raise PublishError(  # noqa: TRY301 - close handle on failure
                    "source is writable by another identity; immutable handoff required: "
                    f"{self.path}"
                )
        except BaseException:
            if self.handle is not None:
                self.root.close_handle(self.handle)
            self.root.close()
            raise

    def read_bounded(self, limit: int) -> bytes:
        if self.size > limit:
            raise PublishError(f"{self.path.name} exceeds its {limit}-byte limit")
        if self.handle is None:
            raise PublishError("source handle is closed")
        content = self.root.read(self.handle, limit)
        if len(content) > limit:
            raise PublishError(f"{self.path.name} grew beyond its {limit}-byte limit")
        return content

    def close(self) -> None:
        if self.handle is not None:
            self.root.close_handle(self.handle)
            self.handle = None
        self.root.close()


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
    if not name or name.endswith((".", " ")):
        return False
    device_basename = name.split(".", maxsplit=1)[0].rstrip(" .").casefold()
    if device_basename in _WINDOWS_RESERVED_DEVICE_NAMES:
        return False
    return bool(
        name not in {".", ".."}
        and "\x00" not in name
        and all(char.isprintable() for char in name)
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


def _publish_checkpoint(_phase: str) -> None:
    """A no-op seam for deterministic interruption tests."""


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


def _publish_location(dest: Path, output_names: set[str]) -> tuple[Path, Path]:
    """Return a safe parent and target, refusing nonempty replacement targets."""
    absolute = dest.expanduser().absolute()
    if not absolute.name:
        raise PublishError("destination must name a directory below its parent")
    if any(_is_reparse_point(component) for component in (absolute, *absolute.parents)):
        raise PublishError("destination path contains a symlink or reparse point")
    parent = _destination_root(absolute.parent, create=True)
    target = parent / absolute.name
    if _is_reparse_point(target):
        raise PublishError("destination path contains a symlink or reparse point")
    if target.exists():
        existing = _destination_root(target, create=False)
        for name in output_names:
            _check_destination_file(existing / name, existing)
        try:
            next(existing.iterdir())
        except StopIteration:
            pass
        else:
            raise PublishError(
                "destination is not empty; choose a new versioned path for atomic publication"
            )
    return parent, target


def _publish(  # noqa: PLR0912, PLR0913, PLR0915 - validations abort the staging transaction
    dataset: Path,
    dest: Path,
    *,
    teacher: str,
    workspace_rule: str | None = None,
    extras: Iterable[Path] = (),
    source_commit: str | None = None,
    publisher_root: PublisherRoot | None = None,
) -> dict[str, object]:
    """Validate and publish bytes captured through stable source/destination handles."""
    _validate_publish_metadata(teacher, workspace_rule)
    absolute_dest = dest.expanduser().absolute()
    destination_name = absolute_dest.name
    if not _safe_bundle_name(destination_name):
        raise PublishError("destination must name a safe directory below its parent")

    owns_parent = publisher_root is None
    if publisher_root is None:
        try:
            parent = SecureRoot(absolute_dest.parent, writable=True)
        except OSError as exc:
            raise PublishError("could not pin the destination parent; refusing to publish") from exc
    else:
        if absolute_dest.parent != publisher_root.path:
            raise PublishError("safe publisher destination must remain inside its profile root")
        parent = publisher_root._secure_root()  # noqa: SLF001 - publisher capability owns this boundary
    sources: list[_OpenedSource] = []
    stage_handle: int | None = None
    stage_name: str | None = None
    stage_files: list[str] = []
    existing_handle: int | None = None
    promoted = False
    try:
        if not parent.supports_private_staging():
            raise PublishError(  # noqa: TRY301 - abort staging transaction
                "destination filesystem cannot enforce private staging; refusing publication"
            )

        sidecar = sidecar_path(dataset)
        source_paths = [dataset, sidecar, *extras]
        source_names = [source.name for source in source_paths]
        folded_names = [name.casefold() for name in source_names]
        if len(set(folded_names)) != len(folded_names):
            raise PublishError("source files have duplicate basenames")  # noqa: TRY301
        if any(name.casefold() in {n.casefold() for n in SELF_DESCRIBING} for name in source_names):
            raise PublishError("a source basename collides with a generated bundle file")  # noqa: TRY301
        if any(not _safe_bundle_name(name) for name in source_names):
            raise PublishError("a source basename is not safe for the bundle")  # noqa: TRY301

        try:
            sources.append(_OpenedSource(dataset))
        except (OSError, PublishError) as exc:
            raise PublishError(f"not a file: {dataset}") from exc
        try:
            sources.append(_OpenedSource(sidecar))
        except (OSError, PublishError) as exc:
            raise PublishError(
                f"provenance sidecar for {dataset.name} is missing or invalid; refusing to publish"
            ) from exc
        for extra in source_paths[2:]:
            try:
                sources.append(_OpenedSource(extra))
            except (OSError, PublishError) as exc:
                raise PublishError(f"not a file: {extra}") from exc
        dataset_source, sidecar_source = sources[:2]
        dataset_bytes = dataset_source.read_bounded(validate_dataset.MAX_DATASET_BYTES)
        sidecar_bytes = sidecar_source.read_bounded(dataset_provenance.MAX_SIDECAR_BYTES)
        snapshots = {dataset.name: dataset_bytes, sidecar.name: sidecar_bytes}
        # These consumers use only the read-only Path methods implemented by this snapshot.
        snapshot_dataset = cast(Path, _SnapshotPath(dataset.name, snapshots))
        try:
            recorded = read_sidecar(snapshot_dataset)
        except ProvenanceError as exc:
            raise PublishError(
                f"provenance sidecar for {dataset.name} is missing or invalid; refusing to publish"
            ) from exc
        try:
            validation = validate_file(snapshot_dataset)
        except Exception as exc:
            raise PublishError("dataset validation failed; refusing to publish") from exc
        if not validation.ok:
            raise PublishError("dataset failed credential/schema validation; refusing to publish")  # noqa: TRY301
        try:
            live_fingerprint = dataset_fingerprint(snapshot_dataset)
        except ProvenanceError as exc:
            raise PublishError("dataset provenance validation failed; refusing to publish") from exc
        if (
            recorded["dataset"] != dataset.name
            or recorded["examples"] != validation.examples
            or recorded["system_prompt_sha256"] != live_fingerprint
        ):
            raise PublishError("provenance sidecar does not match the validated dataset")  # noqa: TRY301

        declared_size = sum(source.size for source in sources)
        if declared_size > MAX_BUNDLE_BYTES:
            raise PublishError(  # noqa: TRY301
                f"bundle sources exceed the {MAX_BUNDLE_BYTES}-byte aggregate bundle byte limit"
            )

        expected: dict[str, str] = {}
        for path, content in ((dataset, dataset_bytes), (sidecar, sidecar_bytes)):
            expected[path.name] = hashlib.sha256(content).hexdigest()

        source_bytes = len(dataset_bytes) + len(sidecar_bytes)
        extra_snapshots: dict[str, bytes] = {}
        for source in sources[2:]:
            remaining = MAX_BUNDLE_BYTES - source_bytes
            snapshot = source.read_bounded(remaining)
            if len(snapshot) != source.size:
                raise PublishError(f"source size changed while reading {source.path.name}")  # noqa: TRY301
            extra_snapshots[source.path.name] = snapshot
            source_bytes += len(snapshot)
            expected[source.path.name] = hashlib.sha256(snapshot).hexdigest()

        sums_text = "".join(f"{value}  {name}\n" for name, value in sorted(expected.items()))
        manifest: dict[str, object] = {
            "dataset": dataset.name,
            "examples": recorded["examples"],
            "system_prompt_sha256": recorded["system_prompt_sha256"],
            "teacher_model": teacher,
            "workspace_rule": workspace_rule,
            "source_commit": source_commit if source_commit is not None else _head_commit(),
            "published_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "files": dict(sorted(expected.items())),
        }
        manifest_text = json.dumps(manifest, indent=2) + "\n"
        generated = {
            SUMS_NAME: sums_text.encode("utf-8"),
            MANIFEST_NAME: manifest_text.encode("utf-8"),
        }
        if len(generated[MANIFEST_NAME]) > MAX_MANIFEST_BYTES:
            raise PublishError(f"{MANIFEST_NAME} exceeds the {MAX_MANIFEST_BYTES}-byte limit")  # noqa: TRY301
        if source_bytes + sum(map(len, generated.values())) > MAX_BUNDLE_BYTES:
            raise PublishError("bundle exceeds the aggregate bundle byte limit")  # noqa: TRY301

        stage_name = _STAGING_PREFIX + secrets.token_hex(12)
        try:
            stage_handle = parent.create_directory(stage_name)
        except OSError as exc:
            raise PublishError("could not create private staging; refusing to publish") from exc
        _publish_checkpoint("stage-created")

        def write_verified(
            name: str, chunks: Iterable[bytes], expected_hash: str | None
        ) -> tuple[int, str]:
            output = parent.create_file(stage_handle, name)
            stage_files.append(name)
            hasher = hashlib.sha256()
            written = 0
            try:
                for chunk in chunks:
                    written += len(chunk)
                    hasher.update(chunk)
                    parent.write(output, chunk)
                source_hash = hasher.hexdigest()
                if expected_hash is not None and source_hash != expected_hash:
                    raise PublishError(f"staged copy does not match the source: {name}")
                parent.flush(output)
                parent.seek_start(output)
                arrived = hashlib.sha256()
                for block in parent.iter_chunks(output):
                    arrived.update(block)
                if arrived.hexdigest() != source_hash:
                    raise PublishError(f"staged copy does not match the source: {name}")
                return written, source_hash
            finally:
                parent.close_handle(output)

        for path, content in ((dataset, dataset_bytes), (sidecar, sidecar_bytes)):
            write_verified(path.name, (content,), expected[path.name])
        _publish_checkpoint("first-payload")

        for source in sources[2:]:
            snapshot = extra_snapshots[source.path.name]
            source_written, source_hash = write_verified(
                source.path.name, (snapshot,), expected[source.path.name]
            )
            if source_written != len(snapshot):
                raise PublishError(f"source size changed while reading {source.path.name}")  # noqa: TRY301
            if source_hash != expected[source.path.name]:
                raise PublishError(  # noqa: TRY301 - reject hash drift inside staging transaction
                    f"staged copy does not match the source: {source.path.name}"
                )
        _publish_checkpoint("all-payloads")
        # Inspect a possible target only after source and aggregate validation.
        # Every inspection is relative to the pinned destination parent.
        try:
            existing_handle = parent.open(destination_name, directory=True)
        except OSError as exc:
            if getattr(exc, "errno", None) == errno.ELOOP:
                raise PublishError("destination path contains a symlink or reparse point") from exc
            if getattr(exc, "errno", None) in {2, 20, 40, 87, 123}:
                existing_handle = None
            else:
                raise PublishError("could not inspect the existing destination") from exc
        if existing_handle is not None:
            for name in (*expected, *generated):
                try:
                    entry = parent.open_child(existing_handle, name)
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise PublishError(
                        f"destination entry is a symlink or reparse point: {name}"
                    ) from exc
                try:
                    _size, links, is_dir = parent.info(entry)
                    if is_dir:
                        raise PublishError(f"destination entry is not a regular file: {name}")
                    if links != 1:
                        raise PublishError(f"destination entry is hard-linked: {name}")
                finally:
                    parent.close_handle(entry)
            try:
                first_entry = next(parent.iter_names(existing_handle, max_entries=1), None)
            except Exception as exc:
                raise PublishError("could not inspect the existing destination") from exc
            if first_entry is not None:
                raise PublishError(  # noqa: TRY301
                    "destination is not empty; choose a new versioned path for atomic publication"
                )
        for name, content in generated.items():
            digest_value = hashlib.sha256(content).hexdigest()
            write_verified(name, (content,), digest_value)
            if name == SUMS_NAME:
                _publish_checkpoint("checksums-written")
            else:
                _publish_checkpoint("manifest-written")
        _publish_checkpoint("verified")

        # Promotion acts on a pinned directory handle and the pinned parent.
        if existing_handle is None:
            _publish_checkpoint("promotion")
            parent.rename_noreplace(stage_handle, stage_name, destination_name)
            promoted = True
        elif sys.platform == "win32":
            raise PublishError(  # noqa: TRY301
                "atomic publication failed; empty destination replacement is unsupported"
            )
        else:
            parent.rename_exchange(stage_handle, stage_name, destination_name, existing_handle)
            promoted = True
            parent.remove_directory(existing_handle, stage_name)
            parent.close_handle(existing_handle)
            existing_handle = None
    except PublishError:
        raise
    except OSError as exc:
        raise PublishError("atomic publication failed; destination was not changed") from exc
    else:
        return manifest
    finally:
        for source in sources:
            source.close()
        if stage_handle is not None:
            if not promoted and stage_name is not None:
                cleanup_error: OSError | None = None
                for name in reversed(stage_files):
                    try:
                        parent.delete_child(stage_handle, name)
                    except OSError as exc:
                        cleanup_error = cleanup_error or exc
                try:
                    parent.remove_directory(stage_handle, stage_name)
                except OSError as exc:
                    cleanup_error = cleanup_error or exc
                if cleanup_error is not None:
                    raise PublishError("secure staging cleanup failed") from cleanup_error
            parent.close_handle(stage_handle)
        if existing_handle is not None:
            parent.close_handle(existing_handle)
        if owns_parent:
            parent.close()


def publish(  # noqa: PLR0913 - compatibility API preserves existing parameters
    dataset: Path,
    dest: Path,
    *,
    teacher: str,
    workspace_rule: str | None = None,
    extras: Iterable[Path] = (),
    source_commit: str | None = None,
) -> dict[str, object]:
    """Deprecated local-only compatibility API accepting an arbitrary path.

    This API does not provide the local-user profile's cross-identity boundary.
    New callers must use :func:`publish_to_root`.
    """
    return _publish(
        dataset,
        dest,
        teacher=teacher,
        workspace_rule=workspace_rule,
        extras=extras,
        source_commit=source_commit,
    )


def publish_to_root(  # noqa: PLR0913 - metadata and source options mirror publish()
    dataset: Path,
    publisher_root: PublisherRoot,
    destination_name: str,
    *,
    teacher: str,
    workspace_rule: str | None = None,
    extras: Iterable[Path] = (),
    source_commit: str | None = None,
) -> dict[str, object]:
    """Publish into one name inside a validated current-user profile."""
    _validate_publish_metadata(teacher, workspace_rule)
    try:
        dest = publisher_root._path_for_display(destination_name)  # noqa: SLF001 - validate profile child
    except OSError as exc:
        raise PublishError("destination must be one safe directory name") from exc
    return _publish(
        dataset,
        dest,
        teacher=teacher,
        workspace_rule=workspace_rule,
        extras=extras,
        source_commit=source_commit,
        publisher_root=publisher_root,
    )


def _iter_sums_lines(content: bytes) -> Iterator[str]:
    """Parse checksum lines from the bounded bytes read through one handle."""
    if len(content) > MAX_SUMS_BYTES:
        raise PublishError(f"{SUMS_NAME} exceeds the {MAX_SUMS_BYTES}-byte verification limit")
    for entries_seen, raw in enumerate(content.splitlines(keepends=True), start=1):
        if len(raw) > MAX_SUMS_LINE_BYTES:
            raise PublishError(
                f"{SUMS_NAME} has a line over the {MAX_SUMS_LINE_BYTES}-byte verification limit"
            )
        if entries_seen > MAX_SUMS_ENTRIES:
            raise PublishError(
                f"{SUMS_NAME} exceeds the {MAX_SUMS_ENTRIES}-entry verification limit"
            )
        try:
            yield raw.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as exc:
            raise PublishError(f"{SUMS_NAME} is not valid UTF-8") from exc


def _parse_sums_line(line: str) -> tuple[str, str] | None:
    """Return the checksum text and safe basename, or None for an invalid record."""
    value, separator, name = line.partition("  ")
    if not separator or not _safe_bundle_name(name):
        return None
    return value, name


def _read_secure_file(root: SecureRoot, name: str, limit: int) -> bytes:
    """Read one bounded regular file from a child handle of the pinned root."""
    handle = root.open(name, immutable=True)
    try:
        size, _links, is_dir = root.info(handle)
        if is_dir:
            raise PublishError(f"{name} must be a regular file")
        if not root.immutable_to_other_users(handle):
            raise PublishError(f"{name} is writable by another identity during verification")
        if size > limit:
            raise PublishError(f"{name} exceeds its {limit}-byte verification limit")
        _verify_checkpoint(f"opened:{name}")
        content = root.read(handle, limit)
        if len(content) != size:
            raise PublishError(f"{name} changed while being verified")
        return content
    finally:
        root.close_handle(handle)


def _verify_checkpoint(_phase: str) -> None:
    """No-op seam for deterministic verification race tests."""


def _verify_sums_entry(
    root: SecureRoot,
    value: str,
    name: str,
    *,
    remaining_bundle_bytes: int,
    snapshot_limit: int | None = None,
) -> tuple[bool, int, bytes | None]:
    """Hash bytes read from one handle and return a bounded snapshot if needed."""
    handle = root.open(name, immutable=True)
    try:
        size, _links, is_dir = root.info(handle)
        if is_dir:
            return False, 0, None
        if not root.immutable_to_other_users(handle):
            raise PublishError(f"{name} is writable by another identity during verification")
        if size > remaining_bundle_bytes:
            raise PublishError(
                f"{SUMS_NAME} exceeds the {MAX_BUNDLE_BYTES}-byte aggregate bundle byte limit"
            )
        _verify_checkpoint(f"opened:{name}")
        snapshot: bytes | None = None
        hasher = hashlib.sha256()
        consumed = 0
        if snapshot_limit is not None:
            if size > snapshot_limit:
                raise PublishError(f"{name} exceeds its {snapshot_limit}-byte validation limit")
            snapshot = root.read(handle, snapshot_limit)
            consumed = len(snapshot)
            hasher.update(snapshot)
        else:
            for block in root.iter_chunks(handle):
                consumed += len(block)
                if consumed > remaining_bundle_bytes:
                    raise PublishError(
                        f"{SUMS_NAME} exceeds the {MAX_BUNDLE_BYTES}-byte aggregate "
                        "bundle byte limit"
                    )
                hasher.update(block)
        if consumed != size:
            return False, consumed, snapshot
        return hasher.hexdigest() == value, consumed, snapshot
    finally:
        root.close_handle(handle)


class _DuplicateManifestKeyError(ValueError):
    """A JSON object contains a key more than once."""


def _unique_manifest_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while refusing duplicate keys at every nesting level."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateManifestKeyError
        result[key] = value
    return result


def _read_manifest(content: bytes) -> tuple[dict[str, object], dict[str, str]]:
    """Parse bytes already read from the pinned manifest handle."""
    if len(content) > MAX_MANIFEST_BYTES:
        raise PublishError(f"{MANIFEST_NAME} exceeds the {MAX_MANIFEST_BYTES}-byte limit")
    try:
        loaded: object = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_manifest_object,
        )
    except _DuplicateManifestKeyError as exc:
        raise PublishError(f"{MANIFEST_NAME} contains duplicate JSON keys") from exc
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise PublishError(f"{MANIFEST_NAME} is missing or invalid") from exc

    required = {
        "dataset",
        "examples",
        "system_prompt_sha256",
        "teacher_model",
        "workspace_rule",
        "source_commit",
        "published_at",
        "files",
    }
    if not isinstance(loaded, dict) or set(loaded) != required:
        raise PublishError(f"{MANIFEST_NAME} has an invalid schema")

    dataset = loaded["dataset"]
    examples = loaded["examples"]
    prompt_digest = loaded["system_prompt_sha256"]
    teacher = loaded["teacher_model"]
    workspace_rule = loaded["workspace_rule"]
    source_commit = loaded["source_commit"]
    published_at = loaded["published_at"]
    raw_files = loaded["files"]
    if (
        not isinstance(dataset, str)
        or not _safe_bundle_name(dataset)
        or dataset.casefold() in {name.casefold() for name in SELF_DESCRIBING}
        or type(examples) is not int
        or examples < 1
        or not isinstance(prompt_digest, str)
        or not _SHA256_PATTERN.fullmatch(prompt_digest)
        or not isinstance(teacher, str)
        or not teacher.strip()
        or not _metadata_text_within_limit(teacher, MAX_TEACHER_MODEL_BYTES)
        or not _metadata_text_within_limit(workspace_rule, MAX_WORKSPACE_RULE_BYTES, optional=True)
        or (
            source_commit is not None
            and (
                not isinstance(source_commit, str)
                or not _GIT_COMMIT_PATTERN.fullmatch(source_commit)
            )
        )
        or not isinstance(published_at, str)
        or not isinstance(raw_files, dict)
    ):
        raise PublishError(f"{MANIFEST_NAME} contains invalid metadata")
    try:
        parsed_published_at = datetime.fromisoformat(published_at)
    except ValueError as exc:
        raise PublishError(f"{MANIFEST_NAME} has an invalid published_at timestamp") from exc
    if parsed_published_at.tzinfo is None or parsed_published_at.utcoffset() != timedelta(0):
        raise PublishError(f"{MANIFEST_NAME} has an invalid published_at timestamp")

    files: dict[str, str] = {}
    folded: set[str] = set()
    for name, value in raw_files.items():
        if (
            not isinstance(name, str)
            or not _safe_bundle_name(name)
            or not isinstance(value, str)
            or not _SHA256_PATTERN.fullmatch(value)
            or name.casefold() in folded
        ):
            raise PublishError(f"{MANIFEST_NAME} has an invalid files mapping")
        folded.add(name.casefold())
        files[name] = value
    return loaded, files


def _validate_manifest_provenance(
    snapshots: dict[str, bytes], manifest: dict[str, object], checksums: dict[str, str]
) -> None:
    """Bind declared dataset identity/count/prompt to its data and sidecar."""
    dataset_name = manifest["dataset"]
    if not isinstance(dataset_name, str):  # validated by _read_manifest
        raise PublishError(f"{MANIFEST_NAME} contains invalid dataset metadata")
    provenance_name = f"{dataset_name}.provenance.json"
    if dataset_name not in checksums or provenance_name not in checksums:
        raise PublishError(f"{MANIFEST_NAME} dataset is not bound to a checksummed sidecar")
    if dataset_name not in snapshots or provenance_name not in snapshots:
        raise PublishError(f"{MANIFEST_NAME} provenance payloads were not pinned")
    dataset_path = cast(Path, _SnapshotPath(dataset_name, snapshots))
    try:
        validation = validate_file(dataset_path)
        recorded = read_sidecar(dataset_path)
        fingerprint = dataset_fingerprint(dataset_path)
    except Exception as exc:
        raise PublishError(f"{MANIFEST_NAME} provenance could not be validated") from exc
    if not validation.ok:
        raise PublishError(f"{MANIFEST_NAME} dataset failed validation")
    if (
        recorded["dataset"] != dataset_name
        or recorded["examples"] != validation.examples
        or recorded["system_prompt_sha256"] != fingerprint
        or manifest["examples"] != validation.examples
        or manifest["system_prompt_sha256"] != fingerprint
    ):
        raise PublishError(
            f"{MANIFEST_NAME} provenance does not match the validated dataset and sidecar"
        )


def _verify_bundle(root: SecureRoot) -> list[str]:  # noqa: PLR0912, PLR0915 - explicit checks
    """Verify a bundle using only names opened relative to the pinned root."""
    try:
        sums_bytes = _read_secure_file(root, SUMS_NAME, MAX_SUMS_BYTES)
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            raise PublishError(f"nothing published here: no {SUMS_NAME}") from exc
        raise PublishError(
            f"{SUMS_NAME} must be a regular file, not a link or special file"
        ) from exc
    lines = list(_iter_sums_lines(sums_bytes))
    try:
        manifest_bytes = _read_secure_file(root, MANIFEST_NAME, MAX_MANIFEST_BYTES)
    except OSError as exc:
        raise PublishError(f"could not inspect {MANIFEST_NAME}") from exc
    _verify_checkpoint(f"read:{MANIFEST_NAME}")
    manifest, manifest_files = _read_manifest(manifest_bytes)

    bundle_bytes = len(sums_bytes) + len(manifest_bytes)
    if bundle_bytes > MAX_BUNDLE_BYTES:
        raise PublishError(
            f"bundle metadata exceeds the {MAX_BUNDLE_BYTES}-byte aggregate bundle byte limit"
        )

    broken: list[str] = []
    seen_names: set[str] = set()
    checksums: dict[str, str] = {}
    snapshots: dict[str, bytes] = {}
    for line in lines:
        if not line.strip():
            continue
        parsed = _parse_sums_line(line)
        if parsed is None:
            _, _, name = line.partition("  ")
            broken.append(name or "[invalid SHA256SUMS entry]")
            continue
        value, name = parsed
        normalized_name = name.casefold()
        if normalized_name in seen_names:
            broken.append(name)
            continue
        seen_names.add(normalized_name)
        if not _SHA256_PATTERN.fullmatch(value):
            broken.append(name)
            continue
        checksums[name] = value

    if checksums != manifest_files:
        raise PublishError(
            f"{MANIFEST_NAME} does not match {SUMS_NAME}; bundle is incomplete or inconsistent"
        )
    if not checksums and not broken:
        raise PublishError("bundle is incomplete: no payload files are listed")

    for name, value in checksums.items():
        snapshot_limit = (
            validate_dataset.MAX_DATASET_BYTES
            if name == manifest["dataset"]
            else dataset_provenance.MAX_SIDECAR_BYTES
            if name == f"{manifest['dataset']}.provenance.json"
            else None
        )
        try:
            valid, consumed, snapshot = _verify_sums_entry(
                root,
                value,
                name,
                remaining_bundle_bytes=MAX_BUNDLE_BYTES - bundle_bytes,
                snapshot_limit=snapshot_limit,
            )
        except OSError:
            valid, consumed, snapshot = False, 0, None
        bundle_bytes += consumed
        if not valid:
            broken.append(name)
        elif snapshot is not None:
            snapshots[name] = snapshot
    if broken:
        return sorted(set(broken))
    _validate_manifest_provenance(snapshots, manifest, checksums)
    return []


def verify(dest: Path) -> list[str]:
    """Deprecated local-only compatibility API accepting an arbitrary path."""
    absolute = dest.expanduser().absolute()
    if absolute.name.startswith(_STAGING_PREFIX):
        raise PublishError("unpublished staging directories cannot be verified as bundles")
    try:
        root = SecureRoot(absolute)
    except OSError as exc:
        raise PublishError("could not pin the bundle directory") from exc
    try:
        return _verify_bundle(root)
    finally:
        root.close()


def verify_from_root(publisher_root: PublisherRoot, destination_name: str) -> list[str]:
    """Verify a committed bundle named inside a validated local-user profile."""
    if not _safe_bundle_name(destination_name) or destination_name.startswith(_STAGING_PREFIX):
        raise PublishError("destination must name a committed bundle inside the profile")
    try:
        publisher_root._path_for_display(destination_name)  # noqa: SLF001 - validate profile child
        root = publisher_root._secure_root().subroot(destination_name)  # noqa: SLF001 - pinned capability
    except OSError as exc:
        raise PublishError("could not safely open the bundle inside the publisher profile") from exc
    try:
        return _verify_bundle(root)
    finally:
        root.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish a dataset and its provenance to a training store."
    )
    # dataset and --teacher are optional for verification, which checks the
    # complete bundle metadata and payloads without needing collection inputs.
    parser.add_argument("dataset", type=Path, nargs="?", help="The exported .jsonl dataset.")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--dest", help="One destination directory name inside the local-user publisher profile."
    )
    destination.add_argument(
        "--local-only-path",
        type=Path,
        help=(
            "Deprecated arbitrary path. Local-only; does not protect against "
            "other local identities."
        ),
    )
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
    if args.local_only_path is None and (args.dest is None or not _safe_bundle_name(args.dest)):
        parser.error("--dest must be one safe directory name inside the local-user profile")

    try:
        if args.local_only_path is not None:
            print(
                "[!] WARNING: --local-only-path is deprecated and provides no "
                "cross-identity destination protection.",
                file=sys.stderr,
            )
            if args.verify_only:
                broken = verify(args.local_only_path)
                print(
                    f"[!] {len(broken)} file(s) bad: {', '.join(broken)}" if broken else "verified"
                )
                return 1 if broken else 0
            manifest = publish(
                args.dataset,
                args.local_only_path,
                teacher=args.teacher,
                workspace_rule=args.workspace_rule,
                extras=tuple(args.also),
            )
            published_path = args.local_only_path
        else:
            with PublisherRoot.provision_local_user() as publisher_root:
                if args.verify_only:
                    broken = verify_from_root(publisher_root, args.dest)
                    print(
                        f"[!] {len(broken)} file(s) bad: {', '.join(broken)}"
                        if broken
                        else "verified"
                    )
                    return 1 if broken else 0
                if args.dataset is None or args.teacher is None:
                    parser.error("dataset and --teacher are required unless --verify-only is given")
                manifest = publish_to_root(
                    args.dataset,
                    publisher_root,
                    args.dest,
                    teacher=args.teacher,
                    workspace_rule=args.workspace_rule,
                    extras=tuple(args.also),
                )
                published_path = publisher_root._path_for_display(args.dest)  # noqa: SLF001 - validated name
    except PublishError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    published = manifest["files"]
    if not isinstance(published, dict):  # pragma: no cover - publish always sets it
        return 1
    print(f"published {len(published)} file(s) to {published_path}")
    for name, value in sorted(published.items()):
        print(f"  {str(value)[:12]}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
