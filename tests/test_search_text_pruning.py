"""``search_text`` must prune a refused branch without changing its output.

The speed is the task and the ordering is the contract. ``MAX_SEARCH_FILES``
is 400 and ``MAX_SEARCH_MATCHES`` is 50, so the candidate order decides which
matches reach the model, and the collected training examples were recorded
against today's order. These three assert the order and the pruning
separately: a golden string, an exact truncated list, and the absence of any
resolution under a branch that was refused at its root.
"""

from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from sandbox import MAX_FILE_BYTES, SandboxError, Workspace, get_workspace, set_workspace
from tools import search_text

#: Deliberately not a word this repository uses: a fixture needle that also
#: occurred in the tree would make a failure ambiguous.
NEEDLE = "pruneme"


def _install(root: Path) -> Iterator[Workspace]:
    installed = Workspace.at(root)
    original = get_workspace()
    set_workspace(installed)
    yield installed
    set_workspace(original)


@pytest.fixture
def mixed(tmp_path: Path) -> Iterator[Workspace]:
    """One of every kind of candidate the walk has to decide about."""
    root = tmp_path / "work"
    root.mkdir()

    # Two matches in one file, and a third in a subdirectory.
    (root / "top.txt").write_text(f"{NEEDLE} one\nquiet\n{NEEDLE} two\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "nested.txt").write_text(f"{NEEDLE} nested\n", encoding="utf-8")

    # Refused: a dot-directory, and -- the reason this fixture is not just
    # dot-prefixed names -- a denied suffix that no startswith('.') rule sees.
    (root / ".hidden").mkdir()
    (root / ".hidden" / "secret.txt").write_text(f"{NEEDLE} hidden\n", encoding="utf-8")
    (root / "secret.key").write_text(f"{NEEDLE} credential\n", encoding="utf-8")

    # Skipped on measurement, not on admission: over the byte limit, and
    # binary by the tool's own sniff.
    (root / "big.txt").write_text(f"{NEEDLE} big\n" + "x" * MAX_FILE_BYTES, encoding="utf-8")
    (root / "blob.bin").write_bytes(b"\0\0" + NEEDLE.encode() + b" binary\n")

    yield from _install(root)


@pytest.fixture
def crowded(tmp_path: Path) -> Iterator[Workspace]:
    """More matches than the limit, spread over directories that sort."""
    root = tmp_path / "work"
    root.mkdir()
    for directory in ("alpha", "beta", "gamma"):
        (root / directory).mkdir()
        for name in ("f1.txt", "f2.txt"):
            lines = "".join(f"{NEEDLE} {index:02d}\n" for index in range(1, 10))
            (root / directory / name).write_text(lines, encoding="utf-8")
    yield from _install(root)


@pytest.fixture
def crowded_dot(tmp_path: Path) -> Iterator[Workspace]:
    """A refused branch holding thousands of entries, and two admitted files."""
    root = tmp_path / "work"
    root.mkdir()
    (root / "visible.txt").write_text(f"{NEEDLE} here\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "also.txt").write_text(f"{NEEDLE} there\n", encoding="utf-8")

    junk = root / ".junk"
    junk.mkdir()
    (junk / "deep").mkdir()
    for index in range(1_000):
        (junk / f"leaf-{index:04d}.txt").write_text(f"{NEEDLE}\n", encoding="utf-8")
        (junk / "deep" / f"leaf-{index:04d}.txt").write_text(f"{NEEDLE}\n", encoding="utf-8")
    yield from _install(root)


# --------------------------------------------------------------------------- #
# 1. the output does not change, byte for byte
# --------------------------------------------------------------------------- #

#: Captured by running the current implementation against the ``mixed``
#: fixture, not written from belief. Every part of it is a decision the walk
#: makes: ``sub/`` before ``top.txt`` is the global path sort, the two
#: ``top.txt`` lines are in line order, and ``.hidden/``, ``secret.key``,
#: ``big.txt`` and ``blob.bin`` are each absent for a different reason. The
#: count in the header is the number of files measured, which includes the
#: binary file that was opened and then rejected.
GOLDEN = (
    "3 matches for 'pruneme':\n"
    "sub/nested.txt:1: pruneme nested\n"
    "top.txt:1: pruneme one\n"
    "top.txt:3: pruneme two"
)


def test_search_text_output_is_byte_identical(mixed: Workspace) -> None:
    assert search_text(NEEDLE) == GOLDEN


# --------------------------------------------------------------------------- #
# 2. the order under truncation
# --------------------------------------------------------------------------- #

#: The exact matches a truncated search returns, captured from the current
#: implementation. This is the test that catches a walk that yields per
#: directory instead of sorting globally: there are 54 matches and the limit
#: is 50, so the last four are the ones the model never sees.
TRUNCATED: tuple[str, ...] = (
    "alpha/f1.txt:1: pruneme 01",
    "alpha/f1.txt:2: pruneme 02",
    "alpha/f1.txt:3: pruneme 03",
    "alpha/f1.txt:4: pruneme 04",
    "alpha/f1.txt:5: pruneme 05",
    "alpha/f1.txt:6: pruneme 06",
    "alpha/f1.txt:7: pruneme 07",
    "alpha/f1.txt:8: pruneme 08",
    "alpha/f1.txt:9: pruneme 09",
    "alpha/f2.txt:1: pruneme 01",
    "alpha/f2.txt:2: pruneme 02",
    "alpha/f2.txt:3: pruneme 03",
    "alpha/f2.txt:4: pruneme 04",
    "alpha/f2.txt:5: pruneme 05",
    "alpha/f2.txt:6: pruneme 06",
    "alpha/f2.txt:7: pruneme 07",
    "alpha/f2.txt:8: pruneme 08",
    "alpha/f2.txt:9: pruneme 09",
    "beta/f1.txt:1: pruneme 01",
    "beta/f1.txt:2: pruneme 02",
    "beta/f1.txt:3: pruneme 03",
    "beta/f1.txt:4: pruneme 04",
    "beta/f1.txt:5: pruneme 05",
    "beta/f1.txt:6: pruneme 06",
    "beta/f1.txt:7: pruneme 07",
    "beta/f1.txt:8: pruneme 08",
    "beta/f1.txt:9: pruneme 09",
    "beta/f2.txt:1: pruneme 01",
    "beta/f2.txt:2: pruneme 02",
    "beta/f2.txt:3: pruneme 03",
    "beta/f2.txt:4: pruneme 04",
    "beta/f2.txt:5: pruneme 05",
    "beta/f2.txt:6: pruneme 06",
    "beta/f2.txt:7: pruneme 07",
    "beta/f2.txt:8: pruneme 08",
    "beta/f2.txt:9: pruneme 09",
    "gamma/f1.txt:1: pruneme 01",
    "gamma/f1.txt:2: pruneme 02",
    "gamma/f1.txt:3: pruneme 03",
    "gamma/f1.txt:4: pruneme 04",
    "gamma/f1.txt:5: pruneme 05",
    "gamma/f1.txt:6: pruneme 06",
    "gamma/f1.txt:7: pruneme 07",
    "gamma/f1.txt:8: pruneme 08",
    "gamma/f1.txt:9: pruneme 09",
    "gamma/f2.txt:1: pruneme 01",
    "gamma/f2.txt:2: pruneme 02",
    "gamma/f2.txt:3: pruneme 03",
    "gamma/f2.txt:4: pruneme 04",
    "gamma/f2.txt:5: pruneme 05",
)


def test_truncation_keeps_the_sorted_order(crowded: Workspace) -> None:
    result = search_text(NEEDLE)
    header, *lines = result.splitlines()

    assert header.endswith("(stopped at the limit):")
    assert tuple(lines) == TRUNCATED


# --------------------------------------------------------------------------- #
# 3. nothing under a refused branch is resolved
# --------------------------------------------------------------------------- #


def test_a_refused_branch_is_not_resolved(
    crowded_dot: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of the change, asserted on calls rather than on a clock.

    A timing assertion would be flaky on CI. What is actually claimed is that
    the 2,001 entries under ``.junk`` are never named: the branch is refused
    once, at its root, and the walk does not descend.
    """
    # Guard the guard: this proves nothing if the branch were admitted.
    with pytest.raises(SandboxError):
        crowded_dot.resolve(".junk")

    asked: list[str] = []
    admitted: list[str] = []
    original_resolve = Workspace.resolve
    original_admit = Workspace.admit_resolved_child

    def recording_resolve(self: Workspace, candidate: str) -> Path:
        asked.append(candidate)
        return original_resolve(self, candidate)

    def recording_admit(self: Workspace, parent: Path, name: str) -> Path:
        admitted.append(self.display(parent / name))
        return original_admit(self, parent, name)

    monkeypatch.setattr(Workspace, "resolve", recording_resolve)
    monkeypatch.setattr(Workspace, "admit_resolved_child", recording_admit)

    result = search_text(NEEDLE)

    assert "visible.txt" in result
    beneath = [candidate for candidate in admitted if candidate.startswith(".junk/")]
    assert beneath == [], f"{len(beneath)} paths examined under a refused branch"
    assert ".junk" in admitted, "the branch itself must be refused at its root"
    assert asked == ["."], f"only the search root should require resolve, got {asked}"
    assert len(admitted) < 10, (
        f"only the admitted tree should be checked, got {len(admitted)} entries"
    )


# --------------------------------------------------------------------------- #
# Stage 2: only reparse points pay for a full resolve
# --------------------------------------------------------------------------- #


def _search_from(
    root: Path,
    query: str,
    *,
    denied: Path | None = None,
    max_bytes: int = MAX_FILE_BYTES,
) -> str:
    old = get_workspace()
    denied_paths = frozenset({denied.resolve()}) if denied is not None else frozenset()
    set_workspace(Workspace.at(root, denied_paths=denied_paths, max_file_bytes=max_bytes))
    try:
        return search_text(query, ".")
    finally:
        set_workspace(old)


def test_search_text_prunes_windows_junction_to_external_directory(tmp_path: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction test requires mklink /J")
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = "b11-junction-outside-only"
    (outside / "junction-secret.txt").write_text(marker, encoding="utf-8")
    junction = root / "junction"
    created = subprocess.run(  # noqa: S603 - fixed local mklink command, pytest-owned paths
        [os.environ["COMSPEC"], "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    try:
        with os.scandir(root) as entries:
            entry = next(entries)
            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
            assert attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT
            assert entry.is_dir(follow_symlinks=False)
            assert not entry.is_symlink(), "fixture must be a junction, not a symlink"
        result = _search_from(root, marker)
        assert result.startswith("No match")
    finally:
        # rmdir removes the junction itself and never traverses its target.
        removed = subprocess.run(  # noqa: S603 - fixed local rmdir command, pytest-owned path
            [os.environ["COMSPEC"], "/c", "rmdir", str(junction)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert removed.returncode == 0, removed.stdout + removed.stderr


def test_search_text_prunes_external_symlink_directory(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = "b11-symlink-directory-outside-only"
    (outside / "secret.txt").write_text(marker, encoding="utf-8")
    link = root / "linked-directory"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    try:
        result = _search_from(root, marker)
        assert result.startswith("No match")
    finally:
        link.unlink(missing_ok=True)


def test_search_text_prunes_external_symlink_file(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    marker = "b11-symlink-file-outside-only"
    outside.write_text(marker, encoding="utf-8")
    link = root / "linked-file.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")
    try:
        result = _search_from(root, marker)
        assert result.startswith("No match")
    finally:
        link.unlink(missing_ok=True)


def test_search_text_still_refuses_a_denied_directory(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    denied = root / "private"
    denied.mkdir(parents=True)
    marker = "b11-denied-only"
    (denied / "secret.txt").write_text(marker, encoding="utf-8")
    result = _search_from(root, marker, denied=denied)
    assert result.startswith("No match")


def test_search_text_still_prunes_a_hidden_directory(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    hidden = root / ".hidden"
    hidden.mkdir(parents=True)
    marker = "b11-hidden-only"
    (hidden / "secret.txt").write_text(marker, encoding="utf-8")
    result = _search_from(root, marker)
    assert result.startswith("No match")


def test_search_text_still_excludes_an_oversized_file(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    marker = "b11-oversized-only"
    (root / "oversized.txt").write_text(marker + "x" * 64, encoding="utf-8")
    result = _search_from(root, marker, max_bytes=32)
    assert result.startswith("No match")



def test_search_text_keeps_an_in_workspace_file_symlink_match(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    marker = "b11-inside-file-link"
    target = root / "target.txt"
    target.write_text(marker, encoding="utf-8")
    link = root / "alias.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")
    try:
        result = _search_from(root, marker)
        assert result == (
            "2 matches for 'b11-inside-file-link':\n"
            "target.txt:1: b11-inside-file-link\n"
            "target.txt:1: b11-inside-file-link"
        )
    finally:
        link.unlink(missing_ok=True)


def test_search_text_does_not_recurse_into_an_in_workspace_directory_symlink(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    target_dir = root / "target-dir"
    target_dir.mkdir(parents=True)
    marker = "b11-inside-directory-link"
    (target_dir / "target.txt").write_text(marker, encoding="utf-8")
    link = root / "alias-dir"
    try:
        link.symlink_to(target_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    try:
        result = _search_from(root, marker)
        assert result == (
            "1 match for 'b11-inside-directory-link':\n"
            "target-dir/target.txt:1: b11-inside-directory-link"
        )
    finally:
        link.unlink(missing_ok=True)
