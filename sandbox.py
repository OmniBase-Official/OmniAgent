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
Symlinks and junctions out        ``Path.resolve()`` follows them before the
                                  containment check, so the target is what
                                  gets tested, not the link.
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

The workspace root defaults to the current directory and is set once at
startup. Nothing here writes, renames or deletes -- these tools are read-only
by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Largest file the tools will open, in bytes.
MAX_FILE_BYTES = 100_000

#: Largest amount of text handed back to the model from a single read.
MAX_READ_CHARS = 16_000

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


@dataclass(frozen=True)
class Workspace:
    """A directory the file tools may read inside, and nothing beyond it."""

    root: Path
    max_file_bytes: int = MAX_FILE_BYTES
    max_read_chars: int = MAX_READ_CHARS
    denied_paths: frozenset[Path] = field(default_factory=frozenset)
    listing_only_paths: frozenset[Path] = field(default_factory=frozenset)

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
                f"path is outside the workspace ({self.root}); "
                "only files under it can be read"
            )
        if self._is_denied(resolved):
            raise SandboxError("that file is not readable by the agent")
        if self._is_hidden(resolved):
            raise SandboxError(
                "hidden files and directories (anything starting with '.') are not readable"
            )
        if resolved.name.lower() in DENIED_NAMES or resolved.suffix.lower() in DENIED_SUFFIXES:
            raise SandboxError("that file looks like a credential and is not readable")
        return resolved

    def _inside(self, resolved: Path) -> bool:
        return resolved == self.root or resolved.is_relative_to(self.root)

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
        path = self.resolve(candidate)
        if path.is_dir():
            raise SandboxError(f"{self.display(path)} is a directory; use list_directory")
        if not path.is_file():
            raise SandboxError(f"no such file: {self.display(path)}")

        size = path.stat().st_size
        if size > self.max_file_bytes:
            raise SandboxError(
                f"{self.display(path)} is {size} bytes, over the "
                f"{self.max_file_bytes}-byte limit"
            )

        blob = path.read_bytes()
        if b"\0" in blob[:_BINARY_SNIFF_BYTES]:
            raise SandboxError(f"{self.display(path)} looks like a binary file")

        # Normalise line endings. The same file read on Windows and on Linux
        # should produce the same Observation, or the training data picks up the
        # platform it happened to be collected on.
        text = blob.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
        if len(text) > self.max_read_chars:
            text = text[: self.max_read_chars] + TRUNCATION_NOTE.format(
                limit=self.max_read_chars
            )
        return text

    def describe(self, candidate: str) -> FileFacts:
        """Measure a file without returning its contents.

        A model asked how long a file is should not have to read the whole
        thing: on a small context window that one observation can push the
        system prompt out, and the answer is a number we already have. Lines
        are counted by streaming, so this works on files too large to read.
        """
        path = self.resolve(candidate)
        if path.is_dir():
            raise SandboxError(f"{self.display(path)} is a directory; use list_directory")
        if not path.is_file():
            raise SandboxError(f"no such file: {self.display(path)}")

        size = path.stat().st_size
        lines = 0
        first = last = ""
        binary = False
        with path.open("rb") as handle:
            head = handle.read(_BINARY_SNIFF_BYTES)
            binary = b"\0" in head
            handle.seek(0)
            if not binary:
                for raw in handle:
                    text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    lines += 1
                    if lines == 1:
                        first = text
                    last = text
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
        if not path.is_dir():
            raise SandboxError(f"not a directory: {self.display(path)}")

        entries: list[tuple[int, str, str]] = []
        for child in path.iterdir():
            if child.name.startswith("."):
                continue
            if self._is_unnameable(child.resolve()):
                continue  # naming it is a pointer to what it holds
            if child.is_dir():
                entries.append((0, child.name, f"{child.name}/"))
            elif child.is_file():
                entries.append((1, child.name, f"{child.name} ({child.stat().st_size} bytes)"))
        return [label for _, _, label in sorted(entries)]

    def display(self, path: Path) -> str:
        """The path as the model should see it: relative to the workspace."""
        try:
            relative = path.relative_to(self.root)
        except ValueError:  # pragma: no cover - callers pass resolved paths
            return str(path)
        return str(relative).replace("\\", "/") or "."


_workspace: Workspace | None = None



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
    """Install the workspace the file tools will use."""
    global _workspace  # noqa: PLW0603 - module-level singleton by design
    _workspace = workspace


def get_workspace() -> Workspace:
    """The installed workspace, defaulting to the current directory."""
    global _workspace  # noqa: PLW0603 - module-level singleton by design
    if _workspace is None:
        _workspace = Workspace.at(Path.cwd())
    return _workspace
