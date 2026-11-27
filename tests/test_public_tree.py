"""docs/pm stays out of the tracked tree (brief 56, owner ruling 53).

The project manager's briefs and notes were removed from the public tree. Local-only
``docs/pm/*-prompt.md`` briefs still live in that folder, untracked. This test fails when any
path under ``docs/pm/`` is tracked again. It blocks a future legitimate tracked document in
that folder on purpose; the owner lifts it by editing ``FORBIDDEN_PREFIX`` below.

``tracked_under`` reads the index with ``git ls-files`` and takes a root, so it is exercised on
throwaway repositories as well as on the real checkout. ``GIT_*`` is scrubbed first: the owner's
pre-push hook exports ``GIT_DIR``, which would make git answer about the hook's repository.

Static: read-only git, no network.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git")
FORBIDDEN_PREFIX = "docs/pm/"


def git_env() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def run_git(root: Path, *args: str) -> bytes:
    assert GIT is not None, "git is required for this test and was not found on PATH"
    done = subprocess.run(  # noqa: S603 - controlled argv; shell=False
        [GIT, "-C", str(root), *args],
        capture_output=True,
        env=git_env(),
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, f"git {args[0]} failed with exit code {done.returncode}"
    return done.stdout


def tracked_under(root: Path, prefix: str = FORBIDDEN_PREFIX) -> list[str]:
    paths = run_git(root, "ls-files", "-z").decode("utf-8", "replace").split("\0")
    return sorted(path for path in paths if path.startswith(prefix))


def make_repo(root: Path) -> Path:
    root.mkdir()
    run_git(root, "init", "-q")
    return root


def put(repo: Path, name: str, *, track: bool) -> None:
    target = repo / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("x\n", encoding="utf-8")
    if track:
        run_git(repo, "add", "-f", "--", name)


def test_the_real_checkout_tracks_nothing_under_docs_pm() -> None:
    assert tracked_under(PROJECT) == [], "docs/pm is local-only; do not track files there"


def test_a_tracked_file_under_docs_pm_is_found(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    put(repo, "docs/pm/x.md", track=True)
    put(repo, "docs/architecture/y.md", track=True)

    assert tracked_under(repo) == ["docs/pm/x.md"]


def test_an_ignored_local_prompt_in_docs_pm_is_fine(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("docs/pm/*-prompt.md\n", encoding="utf-8")
    run_git(repo, "add", ".gitignore")
    put(repo, "docs/pm/y-prompt.md", track=False)

    assert tracked_under(repo) == []
    assert (repo / "docs/pm/y-prompt.md").exists()
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(  # noqa: S603 - a plain add of the ignored file must be refused
            [GIT or "git", "-C", str(repo), "add", "docs/pm/y-prompt.md"],
            env=git_env(),
            check=True,
            capture_output=True,
        )


def test_a_path_that_only_looks_similar_is_not_flagged(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    put(repo, "docs/pmx/a.md", track=True)
    put(repo, "src/docs/pm/b.md", track=True)

    assert tracked_under(repo) == []


def test_inherited_git_variables_do_not_redirect_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-push hook exports GIT_DIR. The check must still read the repository it was given."""
    repo = make_repo(tmp_path / "repo")
    put(repo, "docs/pm/x.md", track=True)
    other = make_repo(tmp_path / "other")
    put(other, "README.md", track=True)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git" / "index"))

    assert tracked_under(repo) == ["docs/pm/x.md"]
