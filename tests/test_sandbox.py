"""Adversarial tests for the filesystem boundary.

Every path here is one a model could plausibly emit -- some by accident, some
because a document it read told it to. The rule being tested is the same each
time: nothing outside the workspace root is reachable, and nothing that smells
like a credential is reachable even inside it.
"""

from __future__ import annotations

import errno
import os
import stat
import subprocess
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest

import sandbox
import securefs
from sandbox import (
    SandboxError,
    Workspace,
    get_workspace,
    set_workspace,
    without_own_transcripts,
    workspace_scope,
)
from securefs import DirectoryLimitError, SecureFSError, SecureRoot
from tools import read_file, search_text


@pytest.fixture
def outside(tmp_path: Path) -> Path:
    """A secret that lives next to the workspace, not inside it."""
    secret = tmp_path / "outside" / "secret.txt"
    secret.parent.mkdir()
    secret.write_text("TOP SECRET", encoding="utf-8")
    return secret


@pytest.fixture
def workspace(tmp_path: Path, outside: Path) -> Workspace:
    root = tmp_path / "work"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text("# Hello\nsecond line\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("def main():\n    return 1\n", encoding="utf-8")
    (root / ".env").write_text("API_KEY=sk-should-never-be-read\n", encoding="utf-8")
    (root / "private.pem").write_text("-----BEGIN PRIVATE KEY-----\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[remote]\n", encoding="utf-8")
    return Workspace.at(root)


# --------------------------------------------------------------------------- #
# escaping the workspace
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "escape",
    [
        "../outside/secret.txt",
        "src/../../outside/secret.txt",
        "./../../outside/secret.txt",
        "../../../../../../../../etc/passwd",
        "..",
        "../",
    ],
)
def test_relative_traversal_is_refused(workspace: Workspace, escape: str) -> None:
    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve(escape)


WINDOWS_STYLE_TRAVERSALS = [
    "..\\outside\\secret.txt",
    "src\\..\\..\\outside\\secret.txt",
    "..\\..\\Windows\\System32\\drivers\\etc\\hosts",
]


@pytest.mark.parametrize("escape", WINDOWS_STYLE_TRAVERSALS)
def test_a_windows_style_traversal_never_reaches_the_secret(
    workspace: Workspace, escape: str
) -> None:
    """The same string is a traversal on one platform and a filename on the other.

    On Windows a backslash separates components, so this walks out of the
    workspace and the containment check refuses it. On POSIX a backslash is an
    ordinary filename character, so the whole string names one file *inside*
    the workspace -- which is not an escape, and resolving it is correct. Two
    earlier versions of this test got that wrong: one asserted the Windows
    error message, the next asserted that resolving always raises. CI on Linux
    caught both.

    What is true on every platform is that the file outside is never returned.
    """
    try:
        text = workspace.read_text(escape)
    except SandboxError:
        return
    assert "TOP SECRET" not in text


@pytest.mark.skipif(sys.platform != "win32", reason="backslash is a separator here")
@pytest.mark.parametrize("escape", WINDOWS_STYLE_TRAVERSALS)
def test_a_windows_style_traversal_is_outside_the_workspace(
    workspace: Workspace, escape: str
) -> None:
    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve(escape)


def test_no_escape_attempt_ever_returns_the_secret(workspace: Workspace, outside: Path) -> None:
    """The property that has to hold on every platform, whatever the message."""
    assert outside.read_text(encoding="utf-8") == "TOP SECRET"

    for attempt in (
        "../outside/secret.txt",
        "..\\outside\\secret.txt",
        "src/../../outside/secret.txt",
        "src\\..\\..\\outside\\secret.txt",
        str(outside),
        "/etc/passwd",
        "\\\\server\\share\\secret.txt",
    ):
        try:
            text = workspace.read_text(attempt)
        except SandboxError:
            continue
        pytest.fail(f"{attempt!r} was readable and returned {text!r}")


def test_an_absolute_path_outside_the_workspace_is_refused(
    workspace: Workspace, outside: Path
) -> None:
    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve(str(outside))


def test_an_absolute_path_inside_the_workspace_is_allowed(workspace: Workspace) -> None:
    resolved = workspace.resolve(str(workspace.root / "README.md"))
    assert resolved == workspace.root / "README.md"


@pytest.mark.parametrize("unc", ["\\\\server\\share\\file.txt", "//server/share/file.txt"])
def test_network_paths_are_refused(workspace: Workspace, unc: str) -> None:
    with pytest.raises(SandboxError, match="UNC and network paths"):
        workspace.resolve(unc)


def test_a_null_byte_in_the_path_is_refused(workspace: Workspace) -> None:
    with pytest.raises(SandboxError, match="null byte"):
        workspace.resolve("README.md\0.txt")


def test_an_empty_path_is_refused(workspace: Workspace) -> None:
    with pytest.raises(SandboxError, match="no path given"):
        workspace.resolve("   ")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows device names")
@pytest.mark.parametrize("device", ["CON", "NUL", "COM1", "\\\\.\\PhysicalDrive0"])
def test_windows_device_names_are_not_readable(workspace: Workspace, device: str) -> None:
    """Refused either as a network path, as outside the workspace, or as not a file."""
    with pytest.raises(SandboxError):
        workspace.read_text(device)


def test_normalised_line_endings(tmp_path: Path) -> None:
    """A CRLF file and an LF file must produce the same Observation."""
    root = tmp_path / "work"
    root.mkdir()
    (root / "crlf.txt").write_bytes(b"one\r\ntwo\r\n")
    (root / "lf.txt").write_bytes(b"one\ntwo\n")
    workspace = Workspace.at(root)

    assert workspace.read_text("crlf.txt") == workspace.read_text("lf.txt") == "one\ntwo\n"


# --------------------------------------------------------------------------- #
# symlinks: the check must test the target, not the link
# --------------------------------------------------------------------------- #


def _can_symlink(tmp_path: Path) -> bool:
    try:
        (tmp_path / "probe_link").symlink_to(tmp_path)
    except (OSError, NotImplementedError):
        return False
    (tmp_path / "probe_link").unlink()
    return True


def test_a_symlink_pointing_out_of_the_workspace_is_refused(
    workspace: Workspace, outside: Path, tmp_path: Path
) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("this environment does not allow creating symlinks")

    link = workspace.root / "innocent.txt"
    link.symlink_to(outside)

    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve("innocent.txt")
    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.read_text_range("innocent.txt", 1, 1)


def test_a_symlinked_directory_out_of_the_workspace_is_refused(
    workspace: Workspace, outside: Path, tmp_path: Path
) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("this environment does not allow creating symlinks")

    link = workspace.root / "elsewhere"
    link.symlink_to(outside.parent, target_is_directory=True)

    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve("elsewhere/secret.txt")


@pytest.mark.parametrize("operation", ["read_text", "read_text_range", "describe", "list_dir"])
def test_hard_links_to_outside_files_are_refused_or_hidden(
    workspace: Workspace, outside: Path, operation: str
) -> None:
    """An in-workspace hard link must not expose an outside file or its metadata."""
    alias = workspace.root / "outside-secret.txt"
    try:
        os.link(outside, alias)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"creating a hard link is unavailable: {exc}")

    if operation == "read_text":
        with pytest.raises(SandboxError, match="hard-linked files"):
            workspace.read_text("outside-secret.txt")
    elif operation == "read_text_range":
        with pytest.raises(SandboxError, match="hard-linked files"):
            workspace.read_text_range("outside-secret.txt", 1, 1)
    elif operation == "describe":
        with pytest.raises(SandboxError, match="hard-linked files"):
            workspace.describe("outside-secret.txt")
    else:
        assert all("outside-secret.txt" not in entry for entry in workspace.list_dir("."))


# --------------------------------------------------------------------------- #
# secrets inside the workspace
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("hidden", [".env", ".git/config", ".git", "src/../.env"])
def test_hidden_files_are_refused(workspace: Workspace, hidden: str) -> None:
    with pytest.raises(SandboxError, match="hidden files"):
        workspace.resolve(hidden)


@pytest.mark.parametrize(
    "secret",
    ["private.pem", "server.key", "store.p12", "id_rsa", "id_ed25519", "credentials"],
)
def test_credential_shaped_names_are_refused(workspace: Workspace, secret: str) -> None:
    (workspace.root / secret).write_text("secret", encoding="utf-8")
    with pytest.raises(SandboxError, match="credential"):
        workspace.resolve(secret)


def test_the_active_log_file_cannot_be_read_back(workspace: Workspace) -> None:
    """Otherwise an earlier conversation re-enters the context and the dataset."""
    log = workspace.root / "run.jsonl"
    log.write_text('{"event": "agent.turn.start"}\n', encoding="utf-8")
    guarded = Workspace.at(workspace.root, denied_paths=frozenset({log.resolve()}))

    with pytest.raises(SandboxError, match="not readable by the agent"):
        guarded.resolve("run.jsonl")


def test_denying_a_directory_denies_every_file_under_it(workspace: Workspace) -> None:
    """An evaluation seals a whole transcript directory, not one file at a time.

    Exact membership was not enough: denying `data/` left
    `data/holdout-expects.txt` readable, and the agent was observed answering
    out of it.
    """
    transcripts = workspace.root / "data"
    transcripts.mkdir()
    (transcripts / "expects.txt").write_text("the answer is 42\n", encoding="utf-8")
    sealed = Workspace.at(workspace.root, denied_paths=frozenset({transcripts.resolve()}))

    with pytest.raises(SandboxError, match="not readable by the agent"):
        sealed.resolve("data/expects.txt")


def test_a_denied_directory_is_itself_refused(workspace: Workspace) -> None:
    """Otherwise list_directory on the denied root still reports its contents."""
    transcripts = workspace.root / "data"
    transcripts.mkdir()
    sealed = Workspace.at(workspace.root, denied_paths=frozenset({transcripts.resolve()}))

    with pytest.raises(SandboxError, match="not readable by the agent"):
        sealed.resolve("data")


def test_a_sibling_sharing_a_name_prefix_stays_readable(workspace: Workspace) -> None:
    """A prefix test on strings would deny `database.py` along with `data/`."""
    (workspace.root / "data").mkdir()
    (workspace.root / "database.py").write_text("x = 1\n", encoding="utf-8")
    sealed = Workspace.at(
        workspace.root, denied_paths=frozenset({(workspace.root / "data").resolve()})
    )

    assert sealed.resolve("database.py").name == "database.py"


def test_list_dir_does_not_name_a_denied_entry(workspace: Workspace) -> None:
    """A listing that names the file is a pointer to the answer key."""
    (workspace.root / "data").mkdir()
    (workspace.root / "data" / "expects.txt").write_text("42\n", encoding="utf-8")
    sealed = Workspace.at(
        workspace.root, denied_paths=frozenset({(workspace.root / "data").resolve()})
    )

    entries = sealed.list_dir(".")

    assert "data/" not in entries
    assert any(entry.startswith("README.md") for entry in entries)


# --------------------------------------------------------------------------- #
# resource limits
# --------------------------------------------------------------------------- #


def test_a_large_file_is_refused_before_it_is_read(workspace: Workspace) -> None:
    big = workspace.root / "big.txt"
    big.write_text("x" * 200_000, encoding="utf-8")

    with pytest.raises(SandboxError, match="over the"):
        workspace.read_text("big.txt")
    with pytest.raises(SandboxError, match="over the"):
        workspace.read_text_range("big.txt", 1, 1)


def test_a_binary_file_is_refused(workspace: Workspace) -> None:
    (workspace.root / "image.dat").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d")

    with pytest.raises(SandboxError, match="binary"):
        workspace.read_text("image.dat")
    with pytest.raises(SandboxError, match="binary"):
        workspace.read_text_range("image.dat", 1, 1)


def test_long_text_is_capped_with_a_distinct_marker(tmp_path: Path) -> None:
    """The note must not look like the logger's truncation marker.

    If it did, every file-reading turn would be thrown out of the dataset.
    """
    root = tmp_path / "work"
    root.mkdir()
    (root / "long.txt").write_text("y" * 20_000, encoding="utf-8")
    workspace = Workspace.at(root, max_read_chars=1_000)

    text = workspace.read_text("long.txt")

    assert len(text) < 1_200
    assert "[file truncated at 1000 characters]" in text
    assert "...(truncated" not in text


def test_a_directory_is_not_read_as_a_file(workspace: Workspace) -> None:
    with pytest.raises(SandboxError, match="is a directory"):
        workspace.read_text("src")


def test_a_missing_file_says_so(workspace: Workspace) -> None:
    with pytest.raises(SandboxError, match="no such file"):
        workspace.read_text("nope.txt")


# --------------------------------------------------------------------------- #
# what is allowed
# --------------------------------------------------------------------------- #


def test_a_normal_file_reads(workspace: Workspace) -> None:
    assert workspace.read_text("README.md") == "# Hello\nsecond line\n"


def test_a_ranged_read_returns_one_based_inclusive_lines(workspace: Workspace) -> None:
    result = workspace.read_text_range("README.md", 1, 2)

    assert "lines 1-2 of 2" in result
    assert "    1  # Hello" in result
    assert "    2  second line" in result


@pytest.mark.parametrize(
    ("start_line", "end_line", "message"),
    [
        (0, 1, "line range"),
        (2, 1, "line range"),
        (1, 101, "max 100 lines"),
        (3, 3, "beyond the end"),
        (True, 1, "must be integers"),
    ],
)
def test_a_ranged_read_rejects_invalid_or_unbounded_ranges(
    workspace: Workspace, start_line: int, end_line: int, message: str
) -> None:
    with pytest.raises(SandboxError, match=message):
        workspace.read_text_range("README.md", start_line, end_line)


def test_a_ranged_read_respects_the_output_character_limit(tmp_path: Path) -> None:
    root = tmp_path / "work"
    root.mkdir()
    (root / "text.txt").write_text("content\n", encoding="utf-8")
    workspace = Workspace.at(root, max_read_chars=20)

    with pytest.raises(SandboxError, match="character"):
        workspace.read_text_range("text.txt", 1, 1)


def test_a_ranged_read_refuses_hidden_and_outside_paths(
    workspace: Workspace, outside: Path
) -> None:
    with pytest.raises(SandboxError, match="hidden files"):
        workspace.read_text_range(".env", 1, 1)
    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.read_text_range(str(outside), 1, 1)


def test_a_nested_file_reads(workspace: Workspace) -> None:
    assert "def main" in workspace.read_text("src/app.py")


def test_listing_hides_dot_entries(workspace: Workspace) -> None:
    entries = workspace.list_dir(".")

    assert "src/" in entries
    assert any(entry.startswith("README.md") for entry in entries)
    assert not any(entry.startswith(".") for entry in entries)


def test_secure_directory_enumerator_stops_at_requested_limit(workspace: Workspace) -> None:
    handle = workspace._open_admitted(workspace.root)
    try:
        names = workspace._secure_root.iter_names(handle, max_entries=1)
        next(names)
        with pytest.raises(DirectoryLimitError, match="entry limit"):
            next(names)
    finally:
        workspace._secure_root.close_handle(handle)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux openat2 fd cleanup")
def test_linux_secure_root_closes_root_fd_when_pinning_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure before finalizer registration does not leak the initial root fd."""
    before = len(list(Path("/proc/self/fd").iterdir()))

    def fail_openat2(*_args: object, **_kwargs: object) -> int:
        raise OSError("injected openat2 failure")

    monkeypatch.setattr(SecureRoot, "_openat2", staticmethod(fail_openat2))
    with pytest.raises(OSError, match="injected openat2 failure"):
        SecureRoot(tmp_path)
    after = len(list(Path("/proc/self/fd").iterdir()))
    assert after == before


@pytest.mark.skipif(sys.platform != "linux", reason="Linux openat2 O_PATH flags")
def test_linux_o_path_handles_do_not_request_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """openat2 rejects O_NONBLOCK combined with O_PATH on supported Linux."""
    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    root = SecureRoot(tmp_path)
    openat2_name = "_openat2"
    original_openat2 = cast(Callable[..., int], getattr(SecureRoot, openat2_name))
    path_flags: list[int] = []
    path_flag = int(getattr(os, "O_PATH", 0))
    nonblocking_flag = int(getattr(os, "O_NONBLOCK", 0))

    def capture_flags(
        parent: int,
        path: str,
        *,
        directory: bool = False,
        no_xdev: bool = True,
        flags: int | None = None,
    ) -> int:
        if flags is not None and flags & path_flag:
            path_flags.append(flags)
        return original_openat2(
            parent, path, directory=directory, no_xdev=no_xdev, flags=flags
        )

    monkeypatch.setattr(SecureRoot, "_openat2", staticmethod(capture_flags))
    try:
        handle = root.open("file.txt")
        root.close_handle(handle)
        root_fd_name = "fd"
        root_fd = cast(int, getattr(root, root_fd_name))
        list(root.iter_names(root_fd, max_entries=10))
        handle = root.open_child(root_fd, "file.txt")
        root.close_handle(handle)
    finally:
        root.close()

    assert len(path_flags) == 3
    assert all(not flags & nonblocking_flag for flags in path_flags)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux procfs reopening")
def test_linux_regular_file_open_fails_closed_without_procfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "data.txt"
    path.write_text("content", encoding="utf-8")
    root = SecureRoot(tmp_path)
    original_open = os.open

    def hide_procfs(path_arg: object, *args: object, **kwargs: object) -> int:
        if str(path_arg).startswith("/proc/self/fd/"):
            raise OSError(errno.ENOENT, "procfs unavailable")
        return original_open(path_arg, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(securefs.os, "open", hide_procfs)
    try:
        with pytest.raises(SecureFSError, match="procfs handle reopening is unavailable"):
            root.open(path.name)
    finally:
        root.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux inode identity conversion")
def test_linux_regular_file_open_rejects_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "data.txt"
    path.write_text("content", encoding="utf-8")
    root = SecureRoot(tmp_path)
    original_fstat = os.fstat
    calls = 0

    def mismatch_second_stat(fd: int) -> object:
        nonlocal calls
        calls += 1
        result = original_fstat(fd)
        if calls == 2:
            return type("Stat", (), {"st_dev": result.st_dev + 1, "st_ino": result.st_ino})()
        return result

    monkeypatch.setattr(securefs.os, "fstat", mismatch_second_stat)
    try:
        with pytest.raises(SecureFSError, match="object changed during handle conversion"):
            root.open(path.name)
    finally:
        root.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux source permission policy")
def test_linux_source_owned_by_other_uid_rejects_owner_write_permission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = SecureRoot(tmp_path)
    handle = root.open(".", directory=True)
    get_effective_uid_name = "geteuid"
    metadata = os.stat_result(
        (
            stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP,
            1,
            1,
            1,
            cast(Callable[[], int], getattr(os, get_effective_uid_name))() + 1,
            0,
            0,
            0,
            0,
            0,
        )
    )
    monkeypatch.setattr(securefs.os, "fstat", lambda _handle: metadata)
    try:
        assert not root.immutable_to_other_users(handle)
    finally:
        root.close_handle(handle)
        root.close()


@pytest.mark.skipif(os.name != "nt", reason="NTFS stage share-mode probe")
def test_windows_held_staging_handle_blocks_parent_path_rename_and_delete(
    owner_private_test_root: Path,
) -> None:
    parent = SecureRoot(owner_private_test_root, writable=True)
    stage_name = "held-stage-share-probe"
    moved_name = "held-stage-share-probe-moved"
    stage = parent.create_directory(stage_name)
    original = owner_private_test_root / stage_name
    moved = owner_private_test_root / moved_name
    try:
        for operation in (lambda: original.rename(moved), original.rmdir):
            with pytest.raises(PermissionError) as raised:
                operation()
            assert getattr(raised.value, "winerror", None) == 32
        assert original.is_dir()
        assert not moved.exists()
    finally:
        parent.remove_directory(stage, stage_name)
        parent.close_handle(stage)
        parent.close()


def test_listing_hides_outside_symlink_metadata(workspace: Workspace, outside: Path) -> None:
    alias = workspace.root / "alias.txt"
    try:
        alias.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"creating a symlink is unavailable: {exc}")

    entries = workspace.list_dir(".")

    assert not any(entry.startswith("alias.txt") for entry in entries)


def test_leaf_swap_after_admission_never_reads_outside_canary(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leaf replaced after path admission is rejected at handle-relative open."""
    target = workspace.root / "race.txt"
    target.write_text("inside-original", encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == "race.txt":
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)
    result: list[str] = []

    def read() -> None:
        try:
            result.append(workspace.read_text("race.txt"))
        except SandboxError as exc:
            result.append(str(exc))

    worker = threading.Thread(target=read)
    worker.start()
    assert admitted.wait(timeout=5)
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError as exc:
        swapped.set()
        worker.join(timeout=5)
        pytest.skip(f"file symlink creation unavailable: {exc}")
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(result) == 1
    assert "TOP SECRET" not in result[0]
    assert result[0] != "inside-original"


def test_read_file_size_comes_from_the_opened_object(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Swapping the name after handle inspection cannot change reported size or bytes."""
    original = "inside-object"
    target = workspace.root / "same-handle.txt"
    target.write_text(original, encoding="utf-8")
    inspected = threading.Event()
    swapped = threading.Event()
    original_info = workspace._secure_root.info

    def paused_info(handle: int) -> tuple[int, int, bool]:
        result = original_info(handle)
        if not inspected.is_set():
            inspected.set()
            assert swapped.wait(timeout=5)
        return result

    monkeypatch.setattr(workspace._secure_root, "info", paused_info)
    result: list[str] = []

    def read() -> None:
        with workspace_scope(workspace):
            result.append(read_file("same-handle.txt"))

    worker = threading.Thread(target=read)
    worker.start()
    assert inspected.wait(timeout=5)
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError as exc:
        swapped.set()
        worker.join(timeout=5)
        pytest.skip(f"file symlink creation unavailable: {exc}")
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result == [f"same-handle.txt (1 lines, {len(original)} bytes):\n    1  {original}"]
    assert "TOP SECRET" not in result[0]


def test_search_existence_check_uses_a_secure_handle(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A leaf swapped after search admission is never read to establish existence."""
    canary = "OUTSIDE-SEARCH-CANARY-9381"
    outside.write_text(canary, encoding="utf-8")
    target = workspace.root / "search-race.txt"
    target.write_text("inside-only", encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == "search-race.txt":
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)
    result: list[str] = []

    def search() -> None:
        with workspace_scope(workspace):
            result.append(search_text(canary, "search-race.txt"))

    worker = threading.Thread(target=search)
    worker.start()
    assert admitted.wait(timeout=5)
    target.unlink()
    try:
        target.symlink_to(outside)
    except OSError as exc:
        swapped.set()
        worker.join(timeout=5)
        pytest.skip(f"file symlink creation unavailable: {exc}")
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(result) == 1
    assert "search-race.txt:1:" not in result[0]
    assert "(0 files searched)" in result[0]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction race test")
def test_parent_junction_swap_after_admission_never_reads_outside_canary(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replacing a parent directory with a junction cannot redirect a read."""
    parent = workspace.root / "race-parent"
    parent.mkdir()
    (parent / outside.name).write_text("inside-original", encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == f"race-parent/{outside.name}":
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)
    result: list[str] = []

    def read() -> None:
        try:
            result.append(workspace.read_text(f"race-parent/{outside.name}"))
        except SandboxError as exc:
            result.append(str(exc))

    worker = threading.Thread(target=read)
    worker.start()
    assert admitted.wait(timeout=5)
    parent.rename(workspace.root / "race-parent-old")
    proc = subprocess.run(  # noqa: S603 - fixed cmd with fixture-controlled paths
        ["cmd", "/c", "mklink", "/J", str(parent), str(outside.parent)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        swapped.set()
        worker.join(timeout=5)
        (workspace.root / "race-parent-old").rename(parent)
        pytest.skip(f"junction creation unavailable: {proc.stderr or proc.stdout}")
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert len(result) == 1
    assert "TOP SECRET" not in result[0]
    assert result[0] != "inside-original"
    parent.rmdir()
    (workspace.root / "race-parent-old").rename(parent)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction race test")
def test_root_swap_after_admission_stays_on_pinned_workspace(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A root path replaced by a junction cannot replace the retained root handle."""
    (workspace.root / outside.name).write_text("inside-root", encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == outside.name:
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)
    result: list[str] = []

    def read() -> None:
        try:
            result.append(workspace.read_text(outside.name))
        except SandboxError as exc:
            result.append(str(exc))

    worker = threading.Thread(target=read)
    worker.start()
    assert admitted.wait(timeout=5)
    root = workspace.root
    moved = root.with_name(root.name + "-pinned")
    root.rename(moved)
    proc = subprocess.run(  # noqa: S603 - fixed cmd with fixture-controlled paths
        ["cmd", "/c", "mklink", "/J", str(root), str(outside.parent)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode:
        swapped.set()
        worker.join(timeout=5)
        moved.rename(root)
        pytest.skip(f"junction creation unavailable: {proc.stderr or proc.stdout}")
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result == ["inside-root"]
    root.rmdir()
    moved.rename(root)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux root-handle race test")
def test_linux_root_swap_stays_on_pinned_workspace(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replacing the configured root path cannot redirect its pinned fd."""
    (workspace.root / outside.name).write_text("inside-linux-root", encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == outside.name:
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)
    result: list[str] = []

    def read() -> None:
        try:
            result.append(workspace.read_text(outside.name))
        except SandboxError as exc:
            result.append(str(exc))

    worker = threading.Thread(target=read)
    worker.start()
    assert admitted.wait(timeout=5)
    root = workspace.root
    moved = root.with_name(root.name + "-pinned-linux")
    root.rename(moved)
    root.symlink_to(outside.parent, target_is_directory=True)
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result == ["inside-linux-root"]
    root.unlink()
    moved.rename(root)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux parent-handle race test")
def test_linux_parent_swap_never_reads_outside_canary(
    workspace: Workspace, outside: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A parent symlink swapped after admission is rejected during relative walk."""
    parent = workspace.root / "linux-race-parent"
    parent.mkdir()
    (parent / outside.name).write_text("inside-parent", encoding="utf-8")
    outside_canary = outside.read_text(encoding="utf-8")
    admitted = threading.Event()
    swapped = threading.Event()
    original_open = workspace._secure_root.open
    returned: list[str] = []
    errors: list[str] = []

    def paused_open(relative: str, *, directory: bool = False) -> int:
        if relative == f"linux-race-parent/{outside.name}":
            admitted.set()
            assert swapped.wait(timeout=5)
        return original_open(relative, directory=directory)

    monkeypatch.setattr(workspace._secure_root, "open", paused_open)

    def read() -> None:
        try:
            returned.append(workspace.read_text(f"linux-race-parent/{outside.name}"))
        except SandboxError as exc:
            errors.append(str(exc))

    worker = threading.Thread(target=read)
    worker.start()
    assert admitted.wait(timeout=5)
    parent.rename(workspace.root / "linux-race-parent-old")
    parent.symlink_to(outside.parent, target_is_directory=True)
    swapped.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert swapped.is_set()
    assert parent.is_symlink()
    assert parent.resolve(strict=True) == outside.parent.resolve()
    assert returned == []
    assert len(errors) == 1
    assert outside_canary not in errors[0]
    parent.unlink()
    (workspace.root / "linux-race-parent-old").rename(parent)


def test_listing_puts_directories_first(workspace: Workspace) -> None:
    (workspace.root / "zzz").mkdir()
    entries = workspace.list_dir(".")

    directories = [i for i, e in enumerate(entries) if e.endswith("/")]
    files = [i for i, e in enumerate(entries) if not e.endswith("/")]
    assert max(directories) < min(files)


def test_listing_refuses_to_return_partial_results_after_entry_limit(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sandbox, "MAX_LIST_DIR_ENTRIES", 3)

    with pytest.raises(SandboxError, match=r"directory listing limit.*no partial listing"):
        workspace.list_dir(".")


def test_listing_refuses_output_over_the_byte_limit(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sandbox, "MAX_LIST_DIR_OUTPUT_BYTES", 4)

    with pytest.raises(SandboxError, match=r"output limit.*no partial listing"):
        workspace.list_dir(".")


def test_listing_replaces_undecodable_posix_filename_bytes(
    workspace: Workspace,
) -> None:
    if os.name != "posix":
        pytest.skip("POSIX undecodable filesystem names are unavailable on this platform")
    raw_name = os.fsencode(workspace.root) + b"/bad-\xff.txt"
    try:
        descriptor = os.open(raw_name, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
    except OSError as exc:
        pytest.skip(f"filesystem does not permit undecodable filename bytes: {exc}")
    else:
        os.close(descriptor)

    entries = workspace.list_dir(".")

    assert any("bad-�.txt" in entry for entry in entries)
    assert all(not any(0xD800 <= ord(char) <= 0xDFFF for char in entry) for entry in entries)


def test_describe_rejects_a_giant_single_line_with_bounded_read(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace.root / "giant-line.txt").write_text("x" * 1_000_000, encoding="utf-8")
    monkeypatch.setattr(sandbox, "MAX_DESCRIBE_LINE_BYTES", 128)

    with pytest.raises(SandboxError, match="describe line limit"):
        workspace.describe("giant-line.txt")


def test_describe_rejects_a_file_over_the_byte_work_limit(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (workspace.root / "many-lines.txt").write_text("x\n" * 100, encoding="utf-8")
    monkeypatch.setattr(sandbox, "MAX_DESCRIBE_BYTES", 64)

    with pytest.raises(SandboxError, match="describe limit"):
        workspace.describe("many-lines.txt")


def test_describe_bounds_first_and_last_line_snippets(workspace: Workspace) -> None:
    (workspace.root / "long-lines.txt").write_text(
        "A" * 5_000 + "\n" + "B" * 5_000, encoding="utf-8"
    )

    facts = workspace.describe("long-lines.txt")

    assert facts.lines == 2
    assert len(facts.first_line) <= sandbox.MAX_DESCRIBE_SNIPPET_CHARS
    assert len(facts.last_line) <= sandbox.MAX_DESCRIBE_SNIPPET_CHARS
    assert facts.first_line.endswith("…")
    assert facts.last_line.startswith("…")


def test_display_is_relative_and_uses_forward_slashes(workspace: Workspace) -> None:
    assert workspace.display(workspace.resolve("src/app.py")) == "src/app.py"
    assert workspace.display(workspace.root) == "."


def test_a_root_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hi", encoding="utf-8")

    with pytest.raises(SandboxError, match="not a directory"):
        Workspace.at(target)


# --------------------------------------------------------------------------- #
# the installed singleton
# --------------------------------------------------------------------------- #


@pytest.fixture
def _restore_workspace() -> Iterator[None]:
    with workspace_scope(Workspace.at(Path.cwd())):
        yield


@pytest.mark.usefixtures("_restore_workspace")
def test_the_workspace_can_be_replaced(workspace: Workspace) -> None:
    set_workspace(workspace)
    assert get_workspace().root == workspace.root


def test_an_unconfigured_workspace_is_refused() -> None:
    with workspace_scope(None), pytest.raises(SandboxError, match="explicit workspace is required"):
        get_workspace()


# --------------------------------------------------------------------------- #
# listing-only: visible from outside, unreadable inside
# --------------------------------------------------------------------------- #


@pytest.fixture
def listing_only(workspace: Workspace) -> Workspace:
    """A transcripts directory the agent may list but not read.

    An evaluation asks "What is inside the data directory?", so the listing is
    the thing being measured; the contents are the thing holding the answers
    to every other question. Sealing both made the question unanswerable by
    construction.
    """
    transcripts = workspace.root / "data"
    (transcripts / "archive").mkdir(parents=True)
    (transcripts / "collect-run.log").write_text("collected\n", encoding="utf-8")
    (transcripts / "holdout-expects.txt").write_text("the answer is 42\n", encoding="utf-8")
    return Workspace.at(workspace.root, listing_only_paths=frozenset({transcripts.resolve()}))


def test_a_listing_only_directory_can_still_be_listed(listing_only: Workspace) -> None:
    entries = listing_only.list_dir("data")

    assert any(entry.startswith("collect-run.log") for entry in entries)


def test_a_listing_only_directory_is_named_by_its_parent(listing_only: Workspace) -> None:
    """Hiding the name would make the question about it unanswerable too."""
    assert "data/" in listing_only.list_dir(".")


def test_a_file_inside_a_listing_only_directory_cannot_be_read(
    listing_only: Workspace,
) -> None:
    """The leak itself: the contents are what held the answers."""
    with pytest.raises(SandboxError, match="not readable by the agent"):
        listing_only.resolve("data/holdout-expects.txt")


def test_a_subdirectory_of_a_listing_only_directory_cannot_be_opened(
    listing_only: Workspace,
) -> None:
    """Otherwise one mkdir reopens the whole leak under a different name."""
    with pytest.raises(SandboxError, match="not readable by the agent"):
        listing_only.resolve("data/archive")


def test_a_listing_only_directory_is_readable_as_a_directory(listing_only: Workspace) -> None:
    """resolve() has to admit the directory itself, or list_dir cannot run."""
    assert listing_only.resolve("data").name == "data"


def test_an_agent_cannot_read_its_earlier_transcripts(tmp_path: Path) -> None:
    """The principle at main.py:265, widened from one log to all of them.

    It already said the agent must not read its own log back, because that
    replays an earlier conversation into the context and into the dataset. A
    sibling log from a previous session does the same thing, and that is not a
    hypothetical: asked where 'budget' was used, the agent answered a line it
    found in an earlier run's transcript rather than reading the file.
    """
    logs = tmp_path / "data"
    logs.mkdir()
    (logs / "earlier.jsonl").write_text('{"answer": "from last time"}\n', encoding="utf-8")
    active = logs / "run.jsonl"
    active.write_text("", encoding="utf-8")
    (tmp_path / "agent.py").write_text("x = 1\n", encoding="utf-8")

    workspace = without_own_transcripts(tmp_path, active)

    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve("data/earlier.jsonl")
    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve("data/run.jsonl")
    assert workspace.resolve("agent.py").name == "agent.py"


def test_the_transcripts_directory_is_still_listable(tmp_path: Path) -> None:
    """Asking what is in it is a fair question; reading them is not."""
    logs = tmp_path / "data"
    logs.mkdir()
    (logs / "notes.log").write_text("x\n", encoding="utf-8")
    workspace = without_own_transcripts(tmp_path, logs / "run.jsonl")

    assert any(entry.startswith("notes.log") for entry in workspace.list_dir("data"))


def test_without_a_log_file_the_default_transcripts_directory_is_used(
    tmp_path: Path,
) -> None:
    """A run with logging off still must not read what earlier runs wrote."""
    logs = tmp_path / "data"
    logs.mkdir()
    (logs / "earlier.jsonl").write_text("{}\n", encoding="utf-8")

    workspace = without_own_transcripts(tmp_path, None)

    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve("data/earlier.jsonl")


def test_a_log_written_into_the_workspace_root_does_not_seal_everything(
    tmp_path: Path,
) -> None:
    """Otherwise pointing the log at the root makes the whole tree unreadable."""
    (tmp_path / "agent.py").write_text("x = 1\n", encoding="utf-8")
    active = tmp_path / "run.jsonl"
    active.write_text("", encoding="utf-8")

    workspace = without_own_transcripts(tmp_path, active)

    assert workspace.resolve("agent.py").name == "agent.py"
    with pytest.raises(SandboxError, match="not readable by the agent"):
        workspace.resolve("run.jsonl")


def test_the_cli_cannot_build_an_unsealed_workspace() -> None:
    """Structural, because the wiring is one line and the logic is elsewhere.

    main.py builds its workspace through without_own_transcripts, which is
    tested above. What is not otherwise covered is the wiring itself: a revert
    to Workspace.at would pass every other test in this file. Reintroducing it
    means reintroducing the import, so this fails on that.
    """
    source = (Path(__file__).resolve().parent.parent / "main.py").read_text("utf-8")

    assert "Workspace.at(" not in source
    assert "without_own_transcripts(" in source
