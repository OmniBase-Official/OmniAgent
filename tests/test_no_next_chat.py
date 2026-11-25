"""NEXT_CHAT.md must never be created again, in any form (owner ruling 30).

Two guards keep the file out, and they fail in different ways, so both are tested:

* ``.gitignore`` stops an accidental ``git add``. Git ignore is case-sensitive, has
  no optional or repeated character and cannot say "files only", so it is a
  best-effort guard: it cannot stop a tracked file and does not touch the disk.
* this test fails if such a file is TRACKED (``git ls-files``) or sits in the
  working tree (a walk of the project root), under any spelling the rule below
  recognises. It is the strong guard.

Only NAMES are read. No file's content is ever opened, and nothing here recreates
the removed file's text. The checker takes a root path, so it is proved on tmp_path
trees. Non-ASCII names are built from code points, so this source stays ASCII.

Static: read-only git, no model, no socket.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import unicodedata
from pathlib import Path, PurePosixPath

import pytest

PROJECT = Path(__file__).resolve().parent.parent
GITIGNORE = PROJECT / ".gitignore"

FORBIDDEN_STEM = "nextchat"

#: An extension that makes a file a note, and a suffix that makes it a backup of one.
NOTE_EXTENSIONS = frozenset({"md", "markdown", "mdx", "txt", "text", "rst"})
BACKUP_SUFFIXES = frozenset({"bak", "old", "orig", "tmp", "copy"})
SUFFIXES = NOTE_EXTENSIONS | BACKUP_SUFFIXES

#: Directories the walk does not enter. Tracked files inside them are still found,
#: because ``git ls-files`` does not prune.
PRUNED = frozenset({".git", ".venv", ".scratch", "node_modules", "models", "data"})

GIT = shutil.which("git")

ADVICE = (
    "NEXT_CHAT.md must never exist in this repository, in any spelling, case or "
    "disguise (owner ruling 30). Delete it (git rm for a tracked file) and do not "
    "recreate it; do not keep a journal at the repository's front door. Found: {found}"
)


def squash(text: str) -> str:
    """Unicode NFKC, lower-cased, with every character that is not a letter or a digit
    removed: spaces, dots, hyphens, underscores, ``~``, zero-width and format
    characters all vanish, and fullwidth letters become ordinary ones."""
    return "".join(
        char for char in unicodedata.normalize("NFKC", text).casefold() if char.isalnum()
    )


def is_forbidden(name: str) -> bool:
    """THE RULE. A file name is forbidden when, after NFKC, its trailing suffixes are
    peeled off from the right for as long as each one is empty, a note-like extension
    (md markdown mdx txt text rst) or a backup suffix (bak old orig tmp copy), and
    what is left SQUASHED equals ``nextchat``.

    The split is not "at the final dot". A final dot that is not a known suffix stays
    inside the stem, so ``NEXT.CHAT`` (no extension) and ``NEXT.CHAT.md`` both leave
    the stem ``NEXT.CHAT``; splitting at the final dot only would read ``NEXT.CHAT``
    as stem ``NEXT`` plus extension ``CHAT`` and miss it. Peeling known suffixes in a
    loop also makes ``NEXT_CHAT.md.bak`` and ``NEXT_CHAT.md.txt`` fall out of one rule.
    """
    rest = unicodedata.normalize("NFKC", name)
    while True:
        base, dot, extension = rest.rpartition(".")
        if not dot or squash(extension) not in (SUFFIXES | {""}):
            break
        rest = base
    return squash(rest) == FORBIDDEN_STEM


def walk_forbidden(root: Path) -> list[str]:
    """Files under *root* whose name the rule forbids. Names only."""
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


def fullwidth(text: str) -> str:
    """The fullwidth form of printable ASCII, e.g. NEXT_CHAT.md spelled with U+FF2E..."""
    return "".join(chr(ord(char) + 0xFEE0) if "!" <= char <= "~" else char for char in text)


ZERO_WIDTH_SPACE = chr(0x200B)

# --------------------------------------------------------------------------- #
# the two tables
# --------------------------------------------------------------------------- #

#: Every one of these is the journal under another spelling, and MUST be caught.
MUST_CATCH = [
    # the original spellings
    "NEXT_CHAT.md", "NEXTCHAT.md", "next_chat.md", "next-chat.md", "NEXT-CHAT.md",
    # case
    "Next_Chat.MD", "next-Chat.md", "nExT_cHaT.Md",
    # repeated or mixed separators
    "NEXT__CHAT.md", "next-_chat.md",
    # other separators: a space, a dot
    "next chat.md", "NEXT.CHAT.md", "NEXT. CHAT.md",
    # other note-like extensions
    "next_chat.markdown", "NEXT_CHAT.mdx", "NEXT_CHAT.txt", "NEXT_CHAT.text", "NEXT_CHAT.rst",
    # no extension at all, with and without a dot in the stem
    "NEXT_CHAT", "nextchat", "NEXT.CHAT", "NEXT CHAT",
    # trailing space, trailing dot, editor tilde
    "next_chat.md ", "NEXT_CHAT.", "NEXT_CHAT.md~", "NEXT_CHAT~",
    # a dot AFTER an extension: only the empty-extension peel reaches the stem
    "NEXT_CHAT.md.", "NEXT_CHAT.md.bak.", "next_chat.txt. ",
    # a second extension, and a backup of it
    "NEXT_CHAT.md.txt", "NEXT_CHAT.md.bak", "NEXT_CHAT.md.bak.txt", "Next_Chat.MD.BAK",
    # a backup suffix directly on the stem
    "NEXT_CHAT.bak", "NEXT_CHAT.old", "NEXT_CHAT.orig", "NEXT_CHAT.tmp", "NEXT_CHAT.copy",
    # disguises: fullwidth, a zero-width space inside the stem or the extension
    fullwidth("NEXT_CHAT.md"),
    fullwidth("next-chat.txt"),
    "NEXT" + ZERO_WIDTH_SPACE + "_CHAT.md",
    "NEXT_CHAT.m" + ZERO_WIDTH_SPACE + "d",
]

#: Fair names that are NOT the journal. The split is by what the NAME says: a
#: different stem is a different file, and a source or data file with this stem is
#: not a note. Known misses, left uncaught on purpose: a note-like file that is
#: merely named something else (next-chat-notes.md), and a type that is not a
#: note-like extension (NEXT_CHAT.docx); the rule can see a name, not a role.
MUST_NOT_CATCH = [
    "NEXT_CHATS.md", "next.md", "chat.md", "nextchat_bot.py", "test_no_next_chat.py",
    "README.md", "MYNEXT_CHAT.md.bak", "next-chat-notes.md", "nextchat2.md", "NEXT_CHAT_2.md",
    "next_chat.py", "NEXT_CHAT.json", "next.chat.py", ".md", "md", "notes.txt",
]

#: Names a file system can hold on every platform, for the on-disk walk. A name with
#: a trailing space or dot cannot be created on Windows, so those stay in MUST_CATCH
#: above, which needs no file.
ON_DISK = [
    "NEXT_CHAT.md", "next-chat.md", "NEXT__CHAT.md", "next chat.md", "NEXT.CHAT.md",
    "next_chat.markdown", "NEXT_CHAT", "NEXT_CHAT.md.bak", "NEXT_CHAT.md.txt", "NEXT_CHAT.bak",
    fullwidth("NEXT_CHAT.md"),
]

#: What the best-effort .gitignore MUST ignore, and what it must leave alone.
GITIGNORED = [
    "NEXT_CHAT.md", "NEXTCHAT.md", "next_chat.md", "next-chat.md", "NEXT-CHAT.md",
    "Next_Chat.MD", "next chat.md", "NEXT.CHAT.md", "next_chat.markdown",
    "NEXT_CHAT.md.txt", "NEXT_CHAT.md.bak", "NEXT_CHAT.md~", "NEXT_CHAT.txt",
    "NEXT_CHAT.text", "NEXT_CHAT.rst", "NEXT_CHAT.bak", "NEXT_CHAT.old", "NEXT_CHAT.orig",
    "NEXT_CHAT.tmp", "NEXT_CHAT.copy", "docs/sub/next-chat.md", "a/b/NEXT.CHAT.md.bak",
    # the no-separator form of every extension, so each generated line has a name
    "NEXTCHAT.markdown", "NEXTCHAT.txt", "NEXTCHAT.text", "NEXTCHAT.rst", "NEXTCHAT.bak",
    "NEXTCHAT.old", "NEXTCHAT.orig", "NEXTCHAT.tmp", "NEXTCHAT.copy",
]
NOT_IGNORED = [
    "NEXT_CHATS.md", "next.md", "chat.md", "nextchat_bot.py", "README.md",
    "MYNEXT_CHAT.md.bak", "test_no_next_chat.py", "next_chat.py",
    # the bare name is NOT ignored on purpose: a pattern for it would also ignore a
    # DIRECTORY of that name and everything in it, so the test guards it instead
    "NEXT_CHAT", "next-chat/notes.txt",
    # two separators in a row: git ignore cannot express "repeated"
    "NEXT__CHAT.md",
]


# --------------------------------------------------------------------------- #
# the rule, on names alone
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", MUST_CATCH, ids=ascii)
def test_every_disguise_of_the_file_is_caught(name: str) -> None:
    assert is_forbidden(name), f"{name!a} slipped past the rule: it is the journal"


@pytest.mark.parametrize("name", MUST_NOT_CATCH, ids=ascii)
def test_a_different_file_is_left_alone(name: str) -> None:
    assert not is_forbidden(name), f"{name!a} was flagged, but it is a different file"


def test_the_two_tables_do_not_overlap() -> None:
    assert not set(MUST_CATCH) & set(MUST_NOT_CATCH)


def test_squash_removes_everything_that_is_not_a_letter_or_a_digit() -> None:
    assert squash(" N-e.x_t" + ZERO_WIDTH_SPACE + "~ ") == "next"
    assert squash(fullwidth("NEXT_CHAT")) == "nextchat"


# --------------------------------------------------------------------------- #
# the repository itself
# --------------------------------------------------------------------------- #


def test_the_repository_has_no_next_chat_file() -> None:
    found = find_forbidden(PROJECT)

    assert found == [], ADVICE.format(found=found)


# --------------------------------------------------------------------------- #
# the working-tree walk
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", ON_DISK, ids=ascii)
def test_the_walk_catches_the_file_on_disk_at_the_root(tmp_path: Path, name: str) -> None:
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


def test_a_tracked_disguise_is_found_through_the_same_rule(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "NEXT_CHAT.md.bak").write_text("decoy\n", encoding="utf-8")
    assert run_git(repo, "add", "NEXT_CHAT.md.bak").returncode == 0

    assert tracked_forbidden(repo) == ["NEXT_CHAT.md.bak"]


def test_a_clean_repository_reports_nothing_tracked(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "README.md").write_text("ok\n", encoding="utf-8")
    assert run_git(repo, "add", "README.md").returncode == 0

    assert tracked_forbidden(repo) == []


def test_a_root_that_is_not_a_repository_has_nothing_tracked(tmp_path: Path) -> None:
    assert tracked_forbidden(tmp_path) == []


# --------------------------------------------------------------------------- #
# the best-effort .gitignore guard
# --------------------------------------------------------------------------- #


def ignored(repo: Path, relative: str) -> bool:
    """Whether the repo's .gitignore ignores *relative*. Exit 0 ignored, 1 not."""
    code = run_git(repo, "check-ignore", "-q", "--", relative).returncode
    assert code in (0, 1), f"git check-ignore failed with {code} for {relative!r}"
    return code == 0


@pytest.fixture
def ignore_repo(tmp_path: Path) -> Path:
    """A scratch repository carrying a copy of THIS project's .gitignore."""
    repo = make_repo(tmp_path / "ignore-repo")
    shutil.copyfile(GITIGNORE, repo / ".gitignore")
    return repo


@pytest.mark.parametrize("name", GITIGNORED, ids=ascii)
def test_the_gitignore_ignores_the_name(ignore_repo: Path, name: str) -> None:
    assert ignored(ignore_repo, name), (
        f".gitignore no longer ignores {name!r}: restore the NEXT_CHAT pattern lines"
    )


@pytest.mark.parametrize("name", NOT_IGNORED, ids=ascii)
def test_the_gitignore_is_not_wider_than_the_file(ignore_repo: Path, name: str) -> None:
    assert not ignored(ignore_repo, name), f".gitignore is ignoring {name!r}, which is not the file"


def test_everything_the_gitignore_ignores_is_something_the_rule_forbids() -> None:
    """A name git silently hides but the test would let through is the dangerous
    direction, so the ignored set must sit inside the forbidden set."""
    leaked = [name for name in GITIGNORED if not is_forbidden(PurePosixPath(name).name)]

    assert leaked == [], f"the .gitignore hides names the rule does not forbid: {leaked}"
