"""Adversarial tests for the filesystem boundary.

Every path here is one a model could plausibly emit -- some by accident, some
because a document it read told it to. The rule being tested is the same each
time: nothing outside the workspace root is reachable, and nothing that smells
like a credential is reachable even inside it.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from sandbox import SandboxError, Workspace, get_workspace, set_workspace


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


def test_no_escape_attempt_ever_returns_the_secret(
    workspace: Workspace, outside: Path
) -> None:
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


def test_a_symlinked_directory_out_of_the_workspace_is_refused(
    workspace: Workspace, outside: Path, tmp_path: Path
) -> None:
    if not _can_symlink(tmp_path):
        pytest.skip("this environment does not allow creating symlinks")

    link = workspace.root / "elsewhere"
    link.symlink_to(outside.parent, target_is_directory=True)

    with pytest.raises(SandboxError, match="outside the workspace"):
        workspace.resolve("elsewhere/secret.txt")


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


def test_a_binary_file_is_refused(workspace: Workspace) -> None:
    (workspace.root / "image.dat").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0d")

    with pytest.raises(SandboxError, match="binary"):
        workspace.read_text("image.dat")


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


def test_a_nested_file_reads(workspace: Workspace) -> None:
    assert "def main" in workspace.read_text("src/app.py")


def test_listing_hides_dot_entries(workspace: Workspace) -> None:
    entries = workspace.list_dir(".")

    assert "src/" in entries
    assert any(entry.startswith("README.md") for entry in entries)
    assert not any(entry.startswith(".") for entry in entries)


def test_listing_puts_directories_first(workspace: Workspace) -> None:
    (workspace.root / "zzz").mkdir()
    entries = workspace.list_dir(".")

    directories = [i for i, e in enumerate(entries) if e.endswith("/")]
    files = [i for i, e in enumerate(entries) if not e.endswith("/")]
    assert max(directories) < min(files)


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
    original = get_workspace()
    yield
    set_workspace(original)


@pytest.mark.usefixtures("_restore_workspace")
def test_the_workspace_can_be_replaced(workspace: Workspace) -> None:
    set_workspace(workspace)
    assert get_workspace().root == workspace.root


def test_the_default_workspace_is_the_current_directory() -> None:
    assert get_workspace().root == Path.cwd().resolve()
