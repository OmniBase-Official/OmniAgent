"""NEXT_CHAT.md must never be created again, in any form (owner ruling 30).

Two guards keep the file out, and they fail in different ways, so both are tested:

* ``.gitignore`` stops an accidental ``git add``. It is case-sensitive, so it uses
  bracket classes, and it has no optional character, so it takes two patterns.
  It cannot stop a file that is already tracked, and it does not touch the disk.
* this test fails if such a file is TRACKED (``git ls-files``) or sits in the
  working tree (a walk of the project root), under any spelling: the name is
  lower-cased and its ``-`` and ``_`` dropped before it is compared, so
  ``NEXT_CHAT.md``, ``NEXTCHAT.md``, ``next-chat.md`` and ``NEXT__CHAT.md`` are
  all caught. That is wider than the two .gitignore patterns on purpose.

Only NAMES are read. No file's content is ever opened, and nothing here recreates
the removed file's text. The checker takes a root path, so it is proved on tmp_path
trees with a decoy for each spelling, a decoy in a subfolder and a clean tree.

Static: read-only git, no model, no socket.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

PROJECT = Path(__file__).resolve().parent.parent
GITIGNORE = PROJECT / ".gitignore"

#: What a forbidden name becomes once lower-cased with ``-`` and ``_`` removed.
FORBIDDEN = "nextchat.md"

#: Directories the walk does not enter. Tracked files inside them are still found,
#: because ``git ls-files`` does not prune.
PRUNED = frozenset({".git", ".venv", ".scratch", "node_modules", "models", "data"})

GIT = shutil.which("git")

SPELLINGS = ["NEXT_CHAT.md", "NEXTCHAT.md", "next_chat.md", "next-chat.md", "NEXT-CHAT.md"]
#: Spellings the .gitignore patterns and this test both cover, beyond the five above.
EXTRA_SPELLINGS = ["Next_Chat.MD", "next-Chat.md"]
#: Spellings only the test catches: repeated or mixed separators.
TEST_ONLY_SPELLINGS = ["NEXT__CHAT.md", "next-_chat.md"]
NOT_THE_FILE = ["NEXT_CHAT.txt", "NEXT_CHATS.md", "next.md", "MYNEXT_CHAT.md.bak", "chat.md"]

ADVICE = (
    "NEXT_CHAT.md must never exist in this repository, in any spelling or case "
    "(owner ruling 30). Delete it (git rm for a tracked file) and do not recreate "
    "it; do not keep a journal at the repository's front door. Found: {found}"
)


def is_forbidden(name: str) -> bool:
    return name.lower().replace("-", "").replace("_", "") == FORBIDDEN


def walk_forbidden(root: Path) -> list[str]:
    """Files under *root* whose name is a spelling of the forbidden one. Names only."""
    found: list[str] = []
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in PRUNED]
        found.extend(
            str(Path(directory, name).relative_to(root)) for name in files if is_forbidden(name)
        )
    return sorted(found)


def _git_env() -> dict[str, str]:
    """The environment without GIT_*: a git hook exports GIT_DIR, which would make
    ``git -C <root>`` answer about the hook's repository instead of *root*."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    if GIT is None:
        pytest.fail("git is required for this test and was not found on PATH")
    return subprocess.run(  # noqa: S603 - controlled argv; shell=False; read-only git
        [GIT, "-C", str(root), *args],
        capture_output=True,
        env=_git_env(),
        check=False,
        timeout=60,
    )


def tracked_forbidden(root: Path) -> list[str]:
    """Tracked files under *root* with a forbidden name. A root that is not a git
    work tree has nothing tracked, so it reports none; a git failure inside one is
    an error, never a silent pass."""
    if not (root / ".git").exists():
        return []
    result = run_git(root, "ls-files", "-z")
    assert result.returncode == 0, f"git ls-files failed: {result.stderr[:200]!r}"
    paths = result.stdout.decode("utf-8", "replace").split("\0")
    return sorted(path for path in paths if path and is_forbidden(PurePosixPath(path).name))


def find_forbidden(root: Path) -> list[str]:
    return sorted(set(tracked_forbidden(root)) | set(walk_forbidden(root)))


def make_repo(root: Path) -> Path:
    root.mkdir()
    assert run_git(root, "init", "-q").returncode == 0
    return root


# --------------------------------------------------------------------------- #
# the repository itself
# --------------------------------------------------------------------------- #


def test_the_repository_has_no_next_chat_file() -> None:
    found = find_forbidden(PROJECT)

    assert found == [], ADVICE.format(found=found)


# --------------------------------------------------------------------------- #
# the working-tree walk
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", [*SPELLINGS, *EXTRA_SPELLINGS, *TEST_ONLY_SPELLINGS])
def test_the_walk_catches_every_spelling_at_the_root(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text("decoy\n", encoding="utf-8")

    assert walk_forbidden(tmp_path) == [name]


def test_the_walk_catches_a_decoy_in_a_subfolder(tmp_path: Path) -> None:
    nested = tmp_path / "docs" / "deep" / "er"
    nested.mkdir(parents=True)
    (nested / "next-chat.md").write_text("decoy\n", encoding="utf-8")

    assert walk_forbidden(tmp_path) == [str(Path("docs", "deep", "er", "next-chat.md"))]


def test_a_clean_tree_reports_nothing(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("ok\n", encoding="utf-8")

    assert walk_forbidden(tmp_path) == []
    assert find_forbidden(tmp_path) == []


@pytest.mark.parametrize("name", NOT_THE_FILE)
def test_names_that_are_not_a_spelling_of_the_file_are_left_alone(
    tmp_path: Path, name: str
) -> None:
    (tmp_path / name).write_text("fine\n", encoding="utf-8")

    assert walk_forbidden(tmp_path) == []


@pytest.mark.parametrize("pruned", sorted(PRUNED))
def test_the_walk_does_not_enter_a_pruned_directory(tmp_path: Path, pruned: str) -> None:
    (tmp_path / pruned).mkdir()
    (tmp_path / pruned / "NEXT_CHAT.md").write_text("decoy\n", encoding="utf-8")

    assert walk_forbidden(tmp_path) == []


# --------------------------------------------------------------------------- #
# tracked files: independent of the walk
# --------------------------------------------------------------------------- #


def test_a_tracked_file_is_found_even_when_it_is_gone_from_the_disk(tmp_path: Path) -> None:
    """Staged and then deleted from the working tree: the walk cannot see it, the
    index still lists it. This is why the tracked check exists at all."""
    repo = make_repo(tmp_path / "repo")
    (repo / "NEXT_CHAT.md").write_text("decoy\n", encoding="utf-8")
    assert run_git(repo, "add", "NEXT_CHAT.md").returncode == 0
    (repo / "NEXT_CHAT.md").unlink()

    assert walk_forbidden(repo) == []
    assert tracked_forbidden(repo) == ["NEXT_CHAT.md"]
    assert find_forbidden(repo) == ["NEXT_CHAT.md"]


def test_a_tracked_file_inside_a_pruned_directory_is_still_found(tmp_path: Path) -> None:
    """The walk prunes models/, but git ls-files does not: a tracked copy there is
    exactly what the walk would miss."""
    repo = make_repo(tmp_path / "repo")
    (repo / "models").mkdir()
    (repo / "models" / "next_chat.md").write_text("decoy\n", encoding="utf-8")
    assert run_git(repo, "add", "-f", "models/next_chat.md").returncode == 0

    assert walk_forbidden(repo) == []
    assert tracked_forbidden(repo) == ["models/next_chat.md"]


def test_a_clean_repository_reports_nothing_tracked(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "README.md").write_text("ok\n", encoding="utf-8")
    assert run_git(repo, "add", "README.md").returncode == 0

    assert tracked_forbidden(repo) == []


def test_a_root_that_is_not_a_repository_has_nothing_tracked(tmp_path: Path) -> None:
    assert tracked_forbidden(tmp_path) == []


# --------------------------------------------------------------------------- #
# the .gitignore guard
# --------------------------------------------------------------------------- #


def ignored(repo: Path, relative: str) -> bool:
    """Whether the repo's .gitignore ignores *relative*. Exit 0 ignored, 1 not."""
    code = run_git(repo, "check-ignore", "-q", relative).returncode
    assert code in (0, 1), f"git check-ignore failed with {code} for {relative}"
    return code == 0


@pytest.fixture
def ignore_repo(tmp_path: Path) -> Path:
    """A scratch repository carrying a copy of THIS project's .gitignore."""
    repo = make_repo(tmp_path / "ignore-repo")
    shutil.copyfile(GITIGNORE, repo / ".gitignore")
    return repo


@pytest.mark.parametrize("name", [*SPELLINGS, *EXTRA_SPELLINGS])
def test_the_gitignore_ignores_every_spelling_at_the_root(ignore_repo: Path, name: str) -> None:
    assert ignored(ignore_repo, name), (
        f".gitignore no longer ignores {name}: restore the two NEXT_CHAT lines"
    )


@pytest.mark.parametrize("name", SPELLINGS)
def test_the_gitignore_ignores_every_spelling_in_a_subfolder(
    ignore_repo: Path, name: str
) -> None:
    assert ignored(ignore_repo, f"docs/sub/{name}")


@pytest.mark.parametrize("name", NOT_THE_FILE)
def test_the_gitignore_is_not_wider_than_the_file(ignore_repo: Path, name: str) -> None:
    assert not ignored(ignore_repo, name), f".gitignore is ignoring {name}, which is not the file"
