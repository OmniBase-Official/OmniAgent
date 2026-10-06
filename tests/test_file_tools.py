"""Tests for the three file tools, as the agent actually calls them.

A refusal has to come back as an ``Error: ...`` Observation, never as an
exception, and never as the contents of something out of bounds.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from agent import AgentConfig, cap_observation
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

    assert result.startswith("README.md (2 lines,")
    assert "    1  # OmniAgent" in result
    assert "    2  A local agent." in result


def test_read_file_states_the_line_count(workspace: Workspace) -> None:
    """Regression from a live run of the fine-tuned model.

    Asked how many lines a 278-line file had, it answered 10,306 -- the file's
    size in bytes, which list_directory had shown it a step earlier. Both
    numbers are now labelled in the header, so neither has to be inferred.
    """
    (workspace.root / "counted.txt").write_text("a\nb\nc\n", encoding="utf-8")

    header = read_file("counted.txt").splitlines()[0]

    assert header.startswith("counted.txt (3 lines, ")
    assert "bytes)" in header


def test_read_file_refuses_rather_than_truncating(workspace: Workspace) -> None:
    """read_file used to truncate here and say so in the header.

    Saying so was not enough. Told only that output had been cut, the model
    went on to answer from the part it could see as though that were the whole
    file, so the truncating branch is gone: anything that will not fit comes
    back as a refusal.
    """
    (workspace.root / "long.txt").write_text("line\n" * 5_000, encoding="utf-8")

    observation = read_file("long.txt")

    assert observation.startswith("Error:")
    assert "too long to return in full" in observation


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
    assert run_tool("read_file", "README.md").startswith("README.md (")
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


# --------------------------------------------------------------------------- #
# a read the agent could not reason over is refused, not trimmed
# --------------------------------------------------------------------------- #


def test_a_file_too_long_to_return_intact_is_refused(
    workspace: Workspace, tmp_path: Path
) -> None:
    """A partial file is worse than no file, because it reads as evidence.

    Three separate fabrications came out of capped reads on the 1.5B: a line
    count copied from the previous turn, "the word 'budget' is not used
    anywhere in the file" about a file that uses it, and a quotation that was
    not in the file at all. An excerpt cannot be told apart from the whole, so
    the model treats what it cannot see as absent. A refusal can only be read
    one way.
    """
    long_file = tmp_path / "work" / "long.py"
    long_file.write_text("\n".join(f"line {number}" for number in range(1, 801)), "utf-8")

    observation = read_file("long.py")

    assert observation.startswith("Error:")
    assert "line 1" not in observation, "a refusal must not smuggle contents out"
    assert "file_info" in observation
    assert "search_text" in observation


def test_a_refused_read_says_how_big_the_file_is(workspace: Workspace, tmp_path: Path) -> None:
    """The refusal is the model's only chance to learn why, so it says."""
    (tmp_path / "work" / "long.py").write_text("x" * 9_000 + "\n", encoding="utf-8")

    observation = read_file("long.py")

    assert "9,001 characters" in observation


def test_read_file_never_returns_more_than_the_agent_will_keep(
    workspace: Workspace, tmp_path: Path
) -> None:
    """The invariant that ties the tool to the loop, instead of a copied number.

    read_file must not hand back something cap_observation would then trim: a
    trimmed read is the thing being removed, so the tool has to stop before
    the loop has to.
    """
    budget = AgentConfig().max_observation_tokens
    for size in (10, 100, 400, 800, 2_000):
        path = tmp_path / "work" / f"f{size}.py"
        path.write_text("\n".join(f"line {number}" for number in range(size)), "utf-8")
        observation = read_file(path.name)
        if observation.startswith("Error:"):
            continue
        assert cap_observation(observation, budget) == observation, f"{size} lines got capped"


# --------------------------------------------------------------------------- #
# a sealed workspace: the answer key out of reach
# --------------------------------------------------------------------------- #


def test_search_text_reports_no_match_inside_a_denied_directory(
    workspace: Workspace, tmp_path: Path
) -> None:
    """The leak this exists to close.

    Asked where 'budget' is used in agent.py, the agent called search_text with
    path "." and its observation came back holding
    `data/holdout-expects.txt:33: The word 'budget' is used in the line
    "agent.budget.exhausted" ...`. It answered that line verbatim -- its own
    earlier answer out of a log, not a reading of agent.py.
    """
    root = tmp_path / "work"
    transcripts = root / "data"
    transcripts.mkdir()
    (transcripts / "holdout-expects.txt").write_text(
        "The word 'budget' is used in the line \"agent.budget.exhausted\".\n",
        encoding="utf-8",
    )

    leaky = search_text("agent.budget.exhausted", ".")
    assert "holdout-expects.txt" in leaky, "fixture does not reproduce the leak"

    set_workspace(Workspace.at(root, denied_paths=frozenset({transcripts.resolve()})))
    sealed = search_text("agent.budget.exhausted", ".")

    assert "holdout-expects.txt" not in sealed
    assert sealed.startswith("No match")


def test_a_denied_directory_cannot_be_searched_by_naming_it(
    workspace: Workspace, tmp_path: Path
) -> None:
    """Sealing the walk is not enough if the directory can be the start of one."""
    root = tmp_path / "work"
    transcripts = root / "data"
    transcripts.mkdir()
    (transcripts / "holdout-expects.txt").write_text("the answer is 42\n", encoding="utf-8")
    set_workspace(Workspace.at(root, denied_paths=frozenset({transcripts.resolve()})))

    observation = search_text("answer", "data")

    assert observation.startswith("Error:")
    assert "not readable by the agent" in observation


def test_list_directory_does_not_name_a_denied_directory(
    workspace: Workspace, tmp_path: Path
) -> None:
    """A listing that names data/ tells the model where to look next."""
    root = tmp_path / "work"
    (root / "data").mkdir()
    set_workspace(Workspace.at(root, denied_paths=frozenset({(root / "data").resolve()})))

    observation = list_directory(".")

    assert "data/" not in observation
    assert "README.md" in observation
