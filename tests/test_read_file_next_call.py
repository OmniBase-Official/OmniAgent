"""Brief 34: the read_file "too long" error ends with the exact next call.

Measured by the project manager over 70 raw rows at 1384d63: on the line-count
question the model never called ``file_info``. It had been told to in three
places -- the ``file_info`` description, the ``read_file`` description and the
oversize error -- and the oversize error said it in general terms ("Use
file_info for size or line facts").

The change is to the text of one tool RESULT, not to a tool description or the
system prompt: the error now ends with the call itself, with this file's path
filled in. These tests pin the cause, not a wording the model happens to like:

* the call names ``file_info`` and carries the path of the file that was
  refused, checked for two different paths so a hard-coded path cannot pass;
* the named call is executable: run exactly as written, it returns the exact
  line count, so the instruction is true and not decorative;
* the error does not itself state a line count (brief 31 tried that, and the
  count was ignored);
* the guidance that was already there -- the ranged read -- is still there.

Static: no model, no socket.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sandbox import Workspace, get_workspace, set_workspace
from tools import read_file, run_tool

LINES = 300
MARKER = "(Action: "
SEPARATOR = ", Action Input: "


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Workspace]:
    root = tmp_path / "workspace"
    (root / "sub").mkdir(parents=True)
    body = "x = 1\n" * LINES
    (root / "alpha.txt").write_text(body, encoding="utf-8")
    (root / "sub" / "beta.txt").write_text(body, encoding="utf-8")
    workspace = Workspace.at(root)
    previous = get_workspace()
    set_workspace(workspace)
    try:
        yield workspace
    finally:
        set_workspace(previous)


def next_call(observation: str) -> tuple[str, str]:
    """The tool name and input the error tells the model to use next."""
    start = observation.index(MARKER) + len(MARKER)
    end = observation.index(")", start)
    name, _, tool_input = observation[start:end].partition(SEPARATOR)
    return name, tool_input


@pytest.mark.parametrize("path", ["alpha.txt", "sub/beta.txt"])
def test_the_error_names_file_info_with_the_path_that_was_refused(
    workspace: Workspace, path: str
) -> None:
    observation = read_file(path)

    assert observation.startswith("Error:")
    assert next_call(observation) == ("file_info", path)


def test_the_named_call_runs_as_written_and_returns_the_exact_line_count(
    workspace: Workspace,
) -> None:
    name, tool_input = next_call(read_file("sub/beta.txt"))

    result = run_tool(name, tool_input)

    assert not result.startswith("Error:")
    assert f"{LINES} lines" in result


def test_the_error_does_not_state_a_line_count_itself(workspace: Workspace) -> None:
    """Brief 31 put the count in the error and it was ignored, 0 of 30. The count
    belongs to the tool that is named, so the error must not carry one."""
    observation = read_file("alpha.txt")

    assert f"{LINES} lines" not in observation
    assert "lines)" not in observation


def test_the_ranged_read_guidance_and_the_refusal_phrase_are_still_there(
    workspace: Workspace,
) -> None:
    observation = read_file("alpha.txt")

    assert "too long to return in full" in observation
    assert "start_line" in observation
    assert "search_text" in observation
