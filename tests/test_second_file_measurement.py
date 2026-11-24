"""The second-file runner must count what it claims to count.

``reached`` is the whole point of the test: a file whose first call is the malformed
``"<path> 1"`` never sees the text under test and must not be scored as if it had. The
expected line count must come from git, and a file that differs between the two commits
must be refused, because an arm comparison on a different file proves nothing.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from second_file_measurement import (
    answer_numbers,
    arm_order,
    expectations,
    first_input,
    reached_oversize,
)

OVERSIZE = (
    "  Observation  : Error: agent.py is 56,479 characters, too long to return in full. "
    "Reading the start of it would not tell you what the rest contains."
)


def test_the_oversize_error_is_reached_only_through_an_observation_line() -> None:
    assert reached_oversize(f"  [step 1]\n  Action       : read_file\n{OVERSIZE}\n") is True
    # The model quoting the phrase in a Thought, or the file merely being malformed, is not it.
    quoted = "  Thought      : the file is too long to return in full, I guess\n"
    assert reached_oversize(quoted) is False
    assert reached_oversize("  Observation  : Error: no such file: observability.py 1\n") is False


def test_first_input_is_the_first_call_not_a_later_one() -> None:
    out = (
        "  Action       : read_file\n  Action Input : observability.py 1\n"
        "  Action       : list_directory\n  Action Input : .\n"
    )
    assert first_input(out) == "observability.py 1"
    assert first_input("  Action Input : config.py\n  Action Input : x\n") == "config.py"
    assert first_input("OmniAgent: no tool at all") is None


def test_answer_numbers_drop_the_thousands_separator() -> None:
    assert answer_numbers("`agent.py` has 1,330 lines.") == ["1330"]
    assert answer_numbers("It has 302 lines (11,050 bytes).") == ["302", "11050"]


def test_the_arm_that_goes_first_alternates() -> None:
    firsts = [arm_order(p, i)[0] for p in (1, 2) for i in (0, 1, 2)]
    assert firsts == ["parent", "child", "parent", "child", "parent", "child"]
    assert all(set(arm_order(p, i)) == {"parent", "child"} for p in (1, 2) for i in (0, 1))


def _repo(path: Path, content: str) -> Path:
    path.mkdir()
    for args in (
        ["init", "-q"],
        ["config", "user.email", "t@example.com"],
        ["config", "user.name", "t"],
    ):
        subprocess.run(["git", "-C", str(path), *args], check=True)  # noqa: S603, S607
    (path / "a.py").write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "a.py"], check=True)  # noqa: S603, S607
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "x"], check=True)  # noqa: S603, S607
    return path


def test_expectation_comes_from_git_and_a_file_that_differs_is_refused(tmp_path: Path) -> None:
    parent = _repo(tmp_path / "p", "one\ntwo\nthree\n")
    same = _repo(tmp_path / "c", "one\ntwo\nthree\n")
    assert expectations(parent, same, ["a.py"]) == {"a.py": "3"}

    # The working copy is edited after the commit: git, not the disk, is the truth.
    (same / "a.py").write_text("x\n" * 99, encoding="utf-8")
    assert expectations(parent, same, ["a.py"]) == {"a.py": "3"}

    other = _repo(tmp_path / "d", "one\ntwo\n")
    with pytest.raises(SystemExit, match="3 lines at the parent and 2 at the child"):
        expectations(parent, other, ["a.py"])
