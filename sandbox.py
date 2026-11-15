"""The filesystem boundary the file tools are allowed to work inside.

Threat model. Everything a tool reads is untrusted input chosen by a language
model, and everything it returns becomes an Observation -- which goes into the
context window, into the log, and from there into the training dataset. So a
path the agent should not reach is not merely a read it should not perform; it
is a leak that gets written down and then trained on.

What is defended against, and how:

================================  ==========================================
Threat                            Mitigation
================================  ==========================================
``../../../etc/passwd``           Resolve, then require the result to sit
``..\\..\\Windows\\System32``       under the workspace root.
Absolute paths outside the root   Same check; an absolute path is allowed
                                  only if it lands inside the workspace.
Symlinks and junctions out        ``Path.resolve()`` informs policy checks;
                                  actual access uses pinned, handle-relative
                                  traversal and rejects reparse points.
Secrets inside the workspace      Dot-files and dot-directories (``.env``,
                                  ``.git``, ``.ssh``) are refused outright,
                                  as are key/certificate suffixes.
The agent reading its own log     The active log file is denied explicitly,
                                  so earlier conversations cannot be fed
                                  back into the context and the dataset.
Huge files exhausting memory      Size is checked before the read, and the
                                  returned text is capped.
Binary files flooding context     A NUL byte in the first chunk rejects it.
Devices (``CON``, ``NUL``,        Only regular files pass; everything else
``\\\\.\\PhysicalDrive0``)            is refused.
UNC paths, NUL bytes in a path    Rejected before resolution.
ReDoS via a search pattern        There is no regex: search is literal
                                  substring matching, so a hostile pattern
                                  has nothing to backtrack over.
================================  ==========================================

Workspace selection is scoped per execution context for agent isolation.
``set_workspace`` remains as a current-context compatibility API; explicit
per-agent workspaces are preferred for new callers. Context variables do not
automatically cross arbitrary thread handoffs; bind the scope in the worker.
Filesystem reads and metadata come from the same opened object. Root and parent
handles remain pinned across concurrent renames; symlinks, reparse points,
mount crossings and special files fail closed. Nothing here writes, renames or
deletes -- these tools are read-only by construction.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from securefs import DirectoryLimitError, SecureRoot

#: Largest file the tools will open, in bytes.
MAX_FILE_BYTES = 100_000

#: Largest amount of text handed back to the model from a single read.
MAX_READ_CHARS = 16_000

# A ranged read is intentionally smaller than the full-file byte limit.
MAX_READ_RANGE_LINES = 100

#: Bounds for metadata tools. The repository has no checked-in dataset or
#: unusually large workspace directories; these limits leave ample headroom
#: over the 47-example dataset documented in README.md.
MAX_LIST_DIR_ENTRIES = 1_000
MAX_LIST_DIR_OUTPUT_BYTES = 128 * 1024
MAX_DESCRIBE_BYTES = 8 * 1024 * 1024
MAX_DESCRIBE_LINE_BYTES = 1024 * 1024
MAX_DESCRIBE_SNIPPET_CHARS = 4_096

#: Deliberately worded so it cannot collide with the logger's own truncation
#: marker, which would disqualify an otherwise fine turn from the dataset.
TRUNCATION_NOTE = "\n[file truncated at {limit} characters]"

#: Bytes sampled when deciding whether a file is binary.
_BINARY_SNIFF_BYTES = 8_000

#: Suffixes that are refused even inside the workspace.
DENIED_SUFFIXES = frozenset(
    {".pem", ".key", ".pfx", ".p12", ".jks", ".keystore", ".crt", ".der", ".asc", ".gpg"}
)

#: Names that are refused even inside the workspace.
DENIED_NAMES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials"})


@dataclass(frozen=True)
class FileFacts:
    """What can be said about a file without quoting it."""

    path: str
    size_bytes: int
    lines: int | None
    first_line: str
    last_line: str
    binary: bool


class SandboxError(ValueError):
    """Raised when a path is outside the workspace or otherwise refused."""


def _line_snippet(raw: bytes, *, from_end: bool) -> str:
    """Decode at most the configured number of characters from one line."""
    limit = MAX_DESCRIBE_SNIPPET_CHARS - 1
    line = raw.rstrip(b"\r\n")
    if len(line) <= limit:
        return line.decode("utf-8", errors="replace")
    if from_end:
        return "…" + line[-limit:].decode("utf-8", errors="replace")
    return line[:limit].decode("utf-8", errors="replace") + "…"


@dataclass(frozen=True)
class Workspace:
    """A directory the file tools may read inside, and nothing beyond it."""

    root: Path
    max_file_bytes: int = MAX_FILE_BYTES
    max_read_chars: int = MAX_READ_CHARS
    denied_paths: frozenset[Path] = field(default_factory=frozenset)
    listing_only_paths: frozenset[Path] = field(default_factory=frozenset)
    _secure_root: SecureRoot = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_secure_root", SecureRoot(self.root))

    @classmethod
    def at(cls, root: Path | str, **kwargs: object) -> Workspace:
        resolved = Path(root).expanduser().resolve()
        if not resolved.is_dir():
            raise SandboxError(f"workspace root is not a directory: {resolved}")
        return cls(root=resolved, **kwargs)  # type: ignore[arg-type]

    # -- path admission ---------------------------------------------------- #

    def resolve(self, candidate: str) -> Path:
        """Resolve a model-supplied path, or refuse it.

        The returned path is absolute, symlink-free and inside the workspace.
        """
        raw = (candidate or "").strip().strip("\"'")
        if not raw:
            raise SandboxError("no path given")
        if "\0" in raw:
            raise SandboxError("path contains a null byte")
        if raw.startswith(("\\\\", "//")):
            raise SandboxError("UNC and network paths are not allowed")

        # Resolve before testing: this is what turns a symlink or a '..' walk
        # into the real target, so the containment check cannot be fooled.
        target = (self.root / raw).expanduser()
        if Path(raw).expanduser().is_absolute():
            target = Path(raw).expanduser()
        resolved = target.resolve()

        if not self._inside(resolved):
            raise SandboxError(
                f"path is outside the workspace ({self.root}); " "only files under it can be read"
            )
        if self._is_denied(resolved):
            raise SandboxError("that file is not readable by the agent")
        if self._is_hidden(resolved):
            raise SandboxError(
                "hidden files and directories (anything starting with '.') are not readable"
            )
        if resolved.name.lower() in DENIED_NAMES or resolved.suffix.lower() in DENIED_SUFFIXES:
            raise SandboxError("that file looks like a credential and is not readable")
        if resolved.is_file() and not self._has_single_link(resolved):
            raise SandboxError("hard-linked files are not readable by the agent")
        return resolved

    @staticmethod
    def _has_single_link(path: Path) -> bool:
        """Fail closed unless a regular file has exactly one filesystem link.

        ``Path.resolve()`` follows symlinks and junctions, but a hard link is a
        second name for the same inode/file record and still resolves inside
        the workspace. Rejecting files with multiple links prevents an
        in-workspace name from exposing bytes also reachable outside it.
        """
        try:
            link_count = path.stat().st_nlink
        except (AttributeError, OSError):
            return False
        return type(link_count) is int and link_count == 1

    def _open_admitted(self, path: Path, *, directory: bool = False) -> int:
        """Open and validate the object through the pinned workspace handle."""
        relative = self.display(path)
        try:
            handle = self._secure_root.open(relative, directory=directory)
        except OSError as exc:
            if not directory:
                try:
                    directory_handle = self._secure_root.open(relative, directory=True)
                except OSError:
                    raise SandboxError(f"no such file: {relative}") from exc
                else:
                    self._secure_root.close_handle(directory_handle)
                    raise SandboxError(f"{relative} is a directory; use list_directory") from exc
            raise SandboxError(f"not a directory: {relative}") from exc
        try:
            _, links, is_dir = self._secure_root.info(handle)
        except BaseException:
            self._secure_root.close_handle(handle)
            raise
        if not is_dir and links != 1:
            self._secure_root.close_handle(handle)
            raise SandboxError("hard-linked files are not readable by the agent")
        if directory and not is_dir:
            self._secure_root.close_handle(handle)
            raise SandboxError(f"not a directory: {self.display(path)}")
        return handle

    def read_bytes(self, candidate: str, limit: int | None = None) -> bytes:
        """Read one regular, single-link file through a pinned handle."""
        path = self.resolve(candidate)
        maximum = self.max_file_bytes if limit is None else limit
        handle = self._open_admitted(path)
        try:
            size, _, is_dir = self._secure_root.info(handle)
            if is_dir:
                raise SandboxError("a directory is not a readable file")
            if size > maximum:
                raise SandboxError("file exceeds the read limit")
            content = self._secure_root.read(handle, maximum)
            if len(content) > maximum:
                raise SandboxError("file grew beyond the read limit")
            return content
        finally:
            self._secure_root.close_handle(handle)

    def secure_exists(self, candidate: str) -> bool:
        """Test existence and readable type by opening handles under the root."""
        path = self.resolve(candidate)
        for directory in (False, True):
            try:
                handle = self._secure_root.open(self.display(path), directory=directory)
            except OSError:
                continue
            try:
                _, links, is_dir = self._secure_root.info(handle)
                if is_dir or links == 1:
                    return True
            finally:
                self._secure_root.close_handle(handle)
        return False

    def secure_files(  # noqa: PLR0912 - each branch enforces a traversal boundary
        self, candidate: str, *, max_entries: int = 10_000
    ) -> list[Path]:
        """List readable files by walking directory handles beneath the root."""
        start = self.resolve(candidate or ".")
        rel = self.display(start)
        try:
            first = self._open_admitted(start, directory=True)
            is_dir = True
        except SandboxError:
            first = self._open_admitted(start)
            is_dir = False
        try:
            # Validate metadata from the handle selected above.
            self._secure_root.info(first)
        finally:
            self._secure_root.close_handle(first)
        if not is_dir:
            return [start]
        pending = [rel]
        found: list[Path] = []
        entries_seen = 0
        while pending:
            parent_rel = pending.pop()
            parent_path = self.root / parent_rel
            directory = self._open_admitted(parent_path, directory=True)
            try:
                for name, _size, _attrs, child_is_dir in self._secure_root.iter_names(
                    directory, max_entries=max_entries - entries_seen
                ):
                    entries_seen += 1
                    if name.startswith("."):
                        continue
                    child_rel = f"{parent_rel}/{name}" if parent_rel != "." else name
                    child_path = self.root / child_rel
                    if self._is_denied(child_path) or self._is_hidden(child_path):
                        continue
                    try:
                        child = self._open_admitted(child_path, directory=child_is_dir)
                    except (OSError, SandboxError):
                        continue
                    try:
                        _, links, actual_dir = self._secure_root.info(child)
                        if actual_dir != child_is_dir or (not actual_dir and links != 1):
                            continue
                    finally:
                        self._secure_root.close_handle(child)
                    if child_is_dir:
                        pending.append(child_rel)
                    else:
                        found.append(child_path)
            except DirectoryLimitError as exc:
                raise OverflowError("secure search traversal limit exceeded") from exc
            finally:
                self._secure_root.close_handle(directory)
        return sorted(found)

    def _inside(self, resolved: Path) -> bool:
        return resolved == self.root or resolved.is_relative_to(self.root)

    def close(self) -> None:
        """Release this workspace's pinned root handle.

        A workspace may be reused in nested scopes. Scope entry and exit never
        close it; its owner closes it only after the final use. Unclosed roots
        are released when the workspace becomes unreachable.
        """
        self._secure_root.close()

    def _is_denied(self, resolved: Path) -> bool:
        """True when the agent may not open this path.

        Two tiers, because an evaluation needs both. A directory in
        :attr:`denied_paths` is gone entirely -- unopenable and unnameable. A
        directory in :attr:`listing_only_paths` may be listed, while nothing
        strictly beneath it may be opened: the evaluation asks what is inside
        the transcripts directory, so the listing is the thing being measured
        while the contents are what hold the answers to every other question.
        Sealing both made that question unanswerable by construction.

        Anything beneath a listing-only directory is refused, subdirectories
        included -- otherwise one ``mkdir`` reopens the leak under a new name.

        Exact membership was the whole test once, which read as an exclusion
        mechanism and was not one: denying ``data/`` left
        ``data/holdout-expects.txt`` readable, and the agent was observed
        answering an evaluation question out of that file verbatim.

        Compared on path components, not on strings -- a string prefix would
        deny ``database.py`` along with ``data/``.
        """
        return self._is_unnameable(resolved) or any(
            resolved != listed and resolved.is_relative_to(listed)
            for listed in self.listing_only_paths
        )

    def _is_unnameable(self, resolved: Path) -> bool:
        """True when the agent may not even be told this path exists.

        Narrower than :meth:`_is_denied` on purpose: a listing-only directory
        has to be named by its parent and has to list its own entries, so
        ``list_dir`` asks this question rather than the opening one.
        """
        return any(
            resolved == denied or resolved.is_relative_to(denied) for denied in self.denied_paths
        )

    def _is_hidden(self, resolved: Path) -> bool:
        try:
            relative = resolved.relative_to(self.root)
        except ValueError:  # pragma: no cover - _inside already ruled this out
            return True
        return any(part.startswith(".") for part in relative.parts)

    # -- reading ----------------------------------------------------------- #

    def read_text(self, candidate: str) -> str:
        """Return a file's text, or raise :class:`SandboxError`."""
        return self.read_text_with_metadata(candidate)[0]

    def read_text_with_metadata(self, candidate: str) -> tuple[str, int, str]:
        """Return text, byte size and display path from one opened file object."""
        path = self.resolve(candidate)
        handle = self._open_admitted(path)
        try:
            size, _, is_dir = self._secure_root.info(handle)
            if is_dir:
                raise SandboxError(f"{self.display(path)} is a directory; use list_directory")
            if size > self.max_file_bytes:
                raise SandboxError(
                    f"{self.display(path)} is {size} bytes, over the "
                    f"{self.max_file_bytes}-byte limit"
                )
            blob = self._secure_root.read(handle, self.max_file_bytes)
            if len(blob) > self.max_file_bytes:
                raise SandboxError(f"{self.display(path)} grew beyond the file size limit")
        finally:
            self._secure_root.close_handle(handle)
        if b"\0" in blob[:_BINARY_SNIFF_BYTES]:
            raise SandboxError(f"{self.display(path)} looks like a binary file")

        # Normalise line endings. The same file read on Windows and on Linux
        # should produce the same Observation, or the training data picks up the
        # platform it happened to be collected on.
        text = blob.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        if len(text) > self.max_read_chars:
            text = text[: self.max_read_chars] + TRUNCATION_NOTE.format(limit=self.max_read_chars)
        return text, size, self.display(path)

    def read_text_range(self, candidate: str, start_line: int, end_line: int) -> str:
        """Return a bounded, numbered line range from an admitted text file."""
        if type(start_line) is not int or type(end_line) is not int:
            raise SandboxError("line numbers must be integers")
        if start_line < 1 or end_line < start_line:
            raise SandboxError("line range must start at 1 or later and end after its start")
        if end_line - start_line + 1 > MAX_READ_RANGE_LINES:
            raise SandboxError(f"line range is too large (max {MAX_READ_RANGE_LINES} lines)")

        path = self.resolve(candidate)
        handle = self._open_admitted(path)
        try:
            size, _, is_dir = self._secure_root.info(handle)
            if is_dir:
                raise SandboxError(f"{self.display(path)} is a directory; use list_directory")
            if size > self.max_file_bytes:
                raise SandboxError(
                    f"{self.display(path)} is {size} bytes, over the "
                    f"{self.max_file_bytes}-byte limit"
                )
            blob = self._secure_root.read(handle, self.max_file_bytes)
            if len(blob) > self.max_file_bytes:
                raise SandboxError(f"{self.display(path)} grew beyond the file size limit")
        finally:
            self._secure_root.close_handle(handle)
        if b"\0" in blob[:_BINARY_SNIFF_BYTES]:
            raise SandboxError(f"{self.display(path)} looks like a binary file")

        text = blob.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        lines = text.splitlines()
        if start_line > len(lines):
            raise SandboxError(
                f"line {start_line} is beyond the end of {self.display(path)} "
                f"({len(lines)} lines)"
            )

        actual_end = min(end_line, len(lines))
        selected = "\n".join(
            f"{number:>5}  {lines[number - 1]}" for number in range(start_line, actual_end + 1)
        )
        rendered = (
            f"{self.display(path)} (lines {start_line}-{actual_end} of {len(lines)}):\n"
            f"{selected}"
        )
        if len(rendered) > self.max_read_chars:
            raise SandboxError(
                f"requested lines from {self.display(path)} exceed the "
                f"{self.max_read_chars}-character limit; request a narrower range"
            )
        return rendered

    def describe(self, candidate: str) -> FileFacts:
        """Measure a file without returning its contents.

        A model asked how long a file is should not have to read the whole
        thing: on a small context window that one observation can push the
        system prompt out, and the answer is a number we already have. Lines
        are counted by streaming, so this works on files too large to read.
        """
        path = self.resolve(candidate)
        handle = self._open_admitted(path)
        try:
            size, _, is_dir = self._secure_root.info(handle)
            if is_dir:
                raise SandboxError(f"{self.display(path)} is a directory; use list_directory")
            blob = self._secure_root.read(handle, MAX_DESCRIBE_BYTES)
        finally:
            self._secure_root.close_handle(handle)
        if size > MAX_DESCRIBE_BYTES:
            raise SandboxError(
                f"{self.display(path)} is {size} bytes, over the "
                f"{MAX_DESCRIBE_BYTES}-byte describe limit"
            )
        lines = 0
        first = last = ""
        binary = False
        binary = b"\0" in blob[:_BINARY_SNIFF_BYTES]
        if not binary:
            bytes_read = 0
            for raw in blob.splitlines(keepends=True):
                bytes_read += len(raw)
                if bytes_read > MAX_DESCRIBE_BYTES:
                    raise SandboxError(
                        f"{self.display(path)} exceeded the "
                        f"{MAX_DESCRIBE_BYTES}-byte describe work limit"
                    )
                if len(raw) > MAX_DESCRIBE_LINE_BYTES:
                    raise SandboxError(
                        f"{self.display(path)} has a line over the "
                        f"{MAX_DESCRIBE_LINE_BYTES}-byte describe line limit"
                    )
                lines += 1
                if lines == 1:
                    first = _line_snippet(raw, from_end=False)
                last = _line_snippet(raw, from_end=True)
        return FileFacts(
            path=self.display(path),
            size_bytes=size,
            lines=None if binary else lines,
            first_line=first,
            last_line=last,
            binary=binary,
        )

    def list_dir(self, candidate: str) -> list[str]:
        """Return the visible entries of a directory, directories first."""
        path = self.resolve(candidate or ".")
        handle = self._open_admitted(path, directory=True)
        entries: list[tuple[int, str, str]] = []
        try:
            children = self._secure_root.iter_names(handle, max_entries=MAX_LIST_DIR_ENTRIES)
            for name, size, _attrs, is_dir in children:
                if _attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    continue
                if name.startswith("."):
                    continue
                child_path = self.root / self.display(path) / name
                if self._is_unnameable(child_path):
                    continue
                label_name = os.fsencode(name).decode("utf-8", errors="replace")
                if is_dir:
                    entries.append((0, name, f"{label_name}/"))
                else:
                    try:
                        child = self._open_admitted(child_path)
                    except (OSError, SandboxError):
                        continue
                    try:
                        _, links, directory = self._secure_root.info(child)
                    finally:
                        self._secure_root.close_handle(child)
                    if not directory and links == 1:
                        entries.append((1, name, f"{label_name} ({size} bytes)"))
        except DirectoryLimitError as exc:
            raise SandboxError(
                f"{self.display(path)} exceeds the {MAX_LIST_DIR_ENTRIES}-entry "
                "directory listing limit; no partial listing is returned"
            ) from exc
        finally:
            self._secure_root.close_handle(handle)
        labels = [label for _, _, label in sorted(entries)]
        output_size = sum(len(label.encode("utf-8", errors="replace")) + 1 for label in labels)
        if output_size > MAX_LIST_DIR_OUTPUT_BYTES:
            raise SandboxError(
                f"{self.display(path)} exceeds the {MAX_LIST_DIR_OUTPUT_BYTES}-byte "
                "directory listing output limit; no partial listing is returned"
            )
        return labels

    def display(self, path: Path) -> str:
        """The path as the model should see it: relative to the workspace."""
        try:
            relative = path.relative_to(self.root)
        except ValueError:  # pragma: no cover - callers pass resolved paths
            return str(path)
        return str(relative).replace("\\", "/") or "."


_workspace_context: ContextVar[Workspace | None] = ContextVar("omniagent_workspace", default=None)


#: Where this project writes its run logs, when a run is not logging to a file
#: of its own. Relative to the workspace root.
TRANSCRIPTS_DIRNAME = "data"


def without_own_transcripts(root: Path, log_file: Path | None) -> Workspace:
    """A workspace in which the agent cannot read any of its own transcripts.

    The rule this widens was already here, stated at the one call site that
    had it: the agent must not read its own log back, because that replays an
    earlier conversation into the context and into the dataset. A *sibling*
    log from a previous session does exactly the same thing, and it is not a
    hypothetical -- asked where the word 'budget' was used in ``agent.py``,
    the agent searched the tree, found the sentence in a previous run's
    transcript and answered that, verbatim. Ten runs with the transcripts out
    of reach: the answer changed and the transcript never appeared in it.

    The directory stays listable, because asking what is inside it is a fair
    question and only reading the contents is the problem. A log written
    straight into the root is denied by name alone -- sealing the root's
    contents would make the whole tree unreadable.
    """
    denied = {log_file.resolve()} if log_file else set()
    transcripts = (log_file.parent if log_file else root / TRANSCRIPTS_DIRNAME).resolve()
    separate = transcripts.is_dir() and transcripts != root.resolve()
    return Workspace.at(
        root,
        denied_paths=frozenset(denied),
        listing_only_paths=frozenset({transcripts} if separate else set()),
    )


def set_workspace(workspace: Workspace) -> None:
    """Set the current execution context's workspace for legacy callers."""
    _workspace_context.set(workspace)


@contextmanager
def workspace_scope(workspace: Workspace | None) -> Iterator[None]:
    """Temporarily select a workspace for this execution context."""
    token = _workspace_context.set(workspace)
    try:
        yield
    finally:
        _workspace_context.reset(token)


def current_workspace() -> Workspace | None:
    """Return the explicitly selected workspace, if this context has one."""
    return _workspace_context.get()


def get_workspace() -> Workspace:
    """Return the explicitly selected workspace or refuse filesystem access."""
    scoped = _workspace_context.get()
    if scoped is None:
        raise SandboxError("an explicit workspace is required for filesystem tools")
    return scoped
