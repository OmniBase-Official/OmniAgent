"""Tests for the three file tools, as the agent actually calls them.

A refusal has to come back as an ``Error: ...`` Observation, never as an
exception, and never as the contents of something out of bounds.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sandbox import Workspace, get_workspace, set_workspace
from tools import list_directory, read_file, run_tool, search_text


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Workspace]:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TOP SECRET", encoding="utf-8")

    root = tmp_path / "work"
    (root / "src").mkdir(parents=True)
    (root / "README.md").write_text("# OmniAgent\nA local agent.\n", encoding="utf-8")
    (root / "src" / "app.py").write_text(
        "def main() -> int:\n    return 0\n\n\nTODO = 'fix later'\n", encoding="utf-8"
    )
    (root / "src" / "util.py").write_text("TODO = 'also here'\n", encoding="utf-8")
    (root / ".env").write_text("API_KEY=sk-never\n", encoding="utf-8")

    installed = Workspace.at(root)
    original = get_workspace()
    set_workspace(installed)
    yield installed
    set_workspace(original)


# --------------------------------------------------------------------------- #
# read_file
# --------------------------------------------------------------------------- #


def test_read_file_numbers_the_lines(workspace: Workspace) -> None:
    result = read_file("README.md")

    assert result.startswith("README.md:")
    assert "    1  # OmniAgent" in result
    assert "    2  A local agent." in result


def test_read_file_reaches_a_nested_path(workspace: Workspace) -> None:
    assert "def main() -> int:" in read_file("src/app.py")


def test_read_file_reports_an_empty_file(workspace: Workspace) -> None:
    (workspace.root / "blank.txt").write_text("", encoding="utf-8")
    assert read_file("blank.txt") == "blank.txt is empty."


@pytest.mark.parametrize(
    "escape",
    ["../outside/secret.txt", "..\\outside\\secret.txt", "src/../../outside/secret.txt"],
)
def test_read_file_refuses_to_escape(workspace: Workspace, escape: str) -> None:
    result = read_file(escape)

    assert result.startswith("Error:")
    assert "TOP SECRET" not in result


def test_read_file_refuses_a_hidden_file(workspace: Workspace) -> None:
    result = read_file(".env")

    assert result.startswith("Error:")
    assert "sk-never" not in result


def test_read_file_refuses_a_directory(workspace: Workspace) -> None:
    assert read_file("src").startswith("Error:")
    assert "list_directory" in read_file("src")


def test_read_file_reports_a_missing_file(workspace: Workspace) -> None:
    assert read_file("nope.txt").startswith("Error:")


# --------------------------------------------------------------------------- #
# list_directory
# --------------------------------------------------------------------------- #


def test_list_directory_defaults_to_the_root(workspace: Workspace) -> None:
    result = list_directory()

    assert result.startswith(".:")
    assert "src/" in result
    assert "README.md" in result
    assert ".env" not in result


def test_list_directory_shows_file_sizes(workspace: Workspace) -> None:
    assert "bytes)" in list_directory(".")


def test_list_directory_reports_an_empty_directory(workspace: Workspace) -> None:
    (workspace.root / "empty").mkdir()
    assert list_directory("empty") == "empty is empty."


def test_list_directory_refuses_to_escape(workspace: Workspace) -> None:
    result = list_directory("../outside")

    assert result.startswith("Error:")
    assert "secret.txt" not in result


def test_list_directory_refuses_a_file(workspace: Workspace) -> None:
    assert list_directory("README.md").startswith("Error:")


# --------------------------------------------------------------------------- #
# search_text
# --------------------------------------------------------------------------- #


def test_search_text_finds_matches_with_file_and_line(workspace: Workspace) -> None:
    result = search_text("TODO")

    assert "src/app.py:5:" in result
    assert "src/util.py:1:" in result
    assert "2 matches" in result


def test_search_text_is_case_insensitive(workspace: Workspace) -> None:
    assert "src/app.py" in search_text("todo")


def test_search_text_can_be_scoped_to_a_path(workspace: Workspace) -> None:
    result = search_text("TODO", "src/util.py")

    assert "src/util.py:1:" in result
    assert "app.py" not in result


def test_search_text_reports_no_match(workspace: Workspace) -> None:
    result = search_text("nothing_matches_this")

    assert result.startswith("No match")
    assert "files searched" in result


def test_search_text_needs_something_to_search_for(workspace: Workspace) -> None:
    assert search_text("   ").startswith("Error: no search text")


def test_search_text_refuses_to_escape(workspace: Workspace) -> None:
    result = search_text("SECRET", "../outside")

    assert result.startswith("Error:")
    assert "TOP SECRET" not in result


def test_search_text_skips_hidden_files(workspace: Workspace) -> None:
    """The .env holds the string but must not be reported."""
    result = search_text("API_KEY")

    assert ".env" not in result
    assert "sk-never" not in result


def test_search_text_skips_binary_files(workspace: Workspace) -> None:
    (workspace.root / "blob.dat").write_bytes(b"TODO\x00\x00binary")
    result = search_text("TODO")

    assert "blob.dat" not in result


def test_search_text_is_literal_not_a_regex(workspace: Workspace) -> None:
    """A hostile regex has nothing to backtrack over if it is taken literally."""
    (workspace.root / "re.txt").write_text("a+b literally\n", encoding="utf-8")

    assert "re.txt:1:" in search_text("a+b")
    assert search_text("(a+)+$").startswith("No match")


def test_search_text_stops_at_the_match_limit(workspace: Workspace) -> None:
    (workspace.root / "many.txt").write_text("hit\n" * 200, encoding="utf-8")
    result = search_text("hit")

    assert "stopped at the limit" in result
    assert result.count("many.txt:") == 50


# --------------------------------------------------------------------------- #
# through the dispatcher, as the agent calls them
# --------------------------------------------------------------------------- #


def test_the_tools_are_reachable_by_name(workspace: Workspace) -> None:
    assert run_tool("read_file", "README.md").startswith("README.md:")
    assert run_tool("list_directory", "none").startswith(".:")
    assert "src/app.py" in run_tool("search_text", '{"query": "def main"}')


def test_search_text_accepts_json_with_both_fields(workspace: Workspace) -> None:
    result = run_tool("search_text", '{"query": "TODO", "path": "src/util.py"}')

    assert "src/util.py:1:" in result
    assert "app.py" not in result


def test_a_bare_value_is_rejected_for_a_two_field_tool(workspace: Workspace) -> None:
    result = run_tool("search_text", "TODO")

    assert result.startswith("Error: invalid arguments")
    assert "JSON object" in result


def test_read_file_requires_a_path(workspace: Workspace) -> None:
    assert run_tool("read_file", "").startswith("Error: invalid arguments")


def test_an_escape_attempt_never_raises_out_of_the_dispatcher(workspace: Workspace) -> None:
    for attempt in ("../outside/secret.txt", "/etc/passwd", "\\\\server\\share\\x"):
        observation = run_tool("read_file", attempt)
        assert observation.startswith("Error:")
        assert "TOP SECRET" not in observation
