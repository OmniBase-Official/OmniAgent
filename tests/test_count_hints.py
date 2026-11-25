"""The hint counter must tell a hint that belongs from one that leaks, and miss none."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from count_hints import candidate, count, steps

NO_SUCH = "Error: no such file: {given}"
HINT = (
    ". Did you mean {path}? Call read_file again with the path only "
    "(Action Input: {path}), no line numbers."
)


def _trace(*calls: tuple[str, str, str]) -> str:
    return "".join(
        f"  [step {i}]\n  Thought : x\n  Action       : {tool}\n  Action Input : {given}\n"
        f"  Observation  : {observed}\n\n"
        for i, (tool, given, observed) in enumerate(calls, start=1)
    )


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    root = tmp_path / "tree"
    (root / "sub").mkdir(parents=True)
    (root / "a.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("x\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("a.py 1", "a.py"),
        ("a.py -1 -1", "a.py"),
        ("a.py\t0\t100", "a.py"),
        ("a.py", None),  # no tail
        ("a.py 1 2 3", None),  # three numbers
        ("a.py 1x", None),
        ("missing.py 1", None),  # candidate does not exist
        ("sub 1", None),  # a directory is not a file
        ("../outside.py 1", None),  # an existing file outside the tree
    ],
)
def test_the_candidate_is_an_existing_file_inside_the_tree(
    tree: Path, given: str, expected: str | None
) -> None:
    assert candidate(given, tree) == expected


def test_a_hint_where_one_belongs_is_shown_and_expected(tree: Path) -> None:
    out = _trace(("read_file", "a.py 1", NO_SUCH.format(given="a.py 1") + HINT.format(path="a.py")))
    assert count(out, tree) == {"shown": 1, "expected": 1, "unexpected": 0, "missing": 0}


def test_a_missing_hint_and_a_leaked_hint_are_both_counted(tree: Path) -> None:
    missing = _trace(("read_file", "a.py 1", NO_SUCH.format(given="a.py 1")))
    assert count(missing, tree) == {"shown": 0, "expected": 1, "unexpected": 0, "missing": 1}
    leaked = _trace(
        (
            "read_file",
            "missing.py 1",
            NO_SUCH.format(given="missing.py 1") + HINT.format(path="missing.py"),
        )
    )
    assert count(leaked, tree) == {"shown": 1, "expected": 0, "unexpected": 1, "missing": 0}


def test_steps_split_the_trace_into_tool_input_observation() -> None:
    out = _trace(
        ("read_file", "a.py", "line one\nline two"), ("file_info", "a.py", "a.py: 1 lines")
    )
    assert steps(out) == [
        ("read_file", "a.py", "line one\nline two"),
        ("file_info", "a.py", "a.py: 1 lines"),
    ]


def test_a_hint_is_expected_only_after_a_no_such_file_error(tree: Path) -> None:
    """The input has a numeric tail and the candidate exists, but the tool did not fail as
    "no such file" (it read the file, or refused it for another reason): no hint belongs."""
    out = _trace(
        ("read_file", "a.py 1", "Error: a.py is too long to return in full."),
        ("file_info", "a.py 1", "a.py: 1 lines, 2 bytes"),
    )
    assert count(out, tree) == {"shown": 0, "expected": 0, "unexpected": 0, "missing": 0}
