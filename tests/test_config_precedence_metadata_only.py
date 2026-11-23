"""C-SE-03: ``inspect_config_precedence`` returns configuration metadata only.

The model can call this tool (it is the seventh in ``FIXED_TOOL_ALLOWLIST``) and
its ``path`` argument is free, so "configuration metadata only" is a claim about
what the tool does with *any* file the sandbox admits, not just ``config.py``.
This file turns that claim into four checks, each built with a canary so that a
green result cannot come from the tool merely refusing:

====  =========================================================================
id    what is shown
====  =========================================================================
M1    process environment values never appear, though a layer is *about* the
      environment
M2    source text outside the layer rows -- constants, comments, other function
      bodies -- never appears
M3    exactly one file is opened: the one named, and no sibling
M4    the error path is bounded like the report (this was a strict xfail that
      recorded a measured defect; brief 33 fixed it and the marker is gone)
====  =========================================================================

What this does not show, and the tests cannot: that the model will not misuse
the report, or anything about prompt injection. Static throughout: no model, no
socket.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from sandbox import Workspace, get_workspace, set_workspace
from tests.test_config_precedence_tool import RESOLVER_SOURCE
from tools import run_tool

#: One distinctive value per place a leak could come from, so a failure names it.
ENV_CANARY = "CANARY-ENV-5c1e07"
CONST_CANARY = "CANARY-CONST-5c1e07"
COMMENT_CANARY = "CANARY-COMMENT-5c1e07"
BODY_CANARY = "CANARY-BODY-5c1e07"
SIBLING_CANARY = "CANARY-SIBLING-5c1e07"

#: The real resolver shape plus content that is NOT a layer row. None of it may
#: reach the report.
CONFIG_WITH_EXTRAS = (
    f'SECRET_NOTE = "{CONST_CANARY}"\n'
    f"# {COMMENT_CANARY}\n"
    + RESOLVER_SOURCE
    + "\n\ndef unrelated_helper() -> str:\n"
    + f'    """{BODY_CANARY}"""\n'
    + f'    return "{BODY_CANARY}"\n'
)

#: A line that the report always carries for a healthy resolver. Every "absent"
#: assertion below is paired with this one, so absence cannot mean "refused".
POSITIVE_CONTROL = "'command line' (configuration layer)"


@pytest.fixture
def workspace(tmp_path: Path) -> Iterator[Workspace]:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "config.py").write_text(CONFIG_WITH_EXTRAS, encoding="utf-8")
    (root / "sibling.py").write_text(f'SIBLING = "{SIBLING_CANARY}"\n', encoding="utf-8")
    (root / "notes.txt").write_text(f"{SIBLING_CANARY}\n", encoding="utf-8")
    workspace = Workspace.at(root)
    previous = get_workspace()
    set_workspace(workspace)
    try:
        yield workspace
    finally:
        set_workspace(previous)


# --------------------------------------------------------------------------- #
# M1 - the environment is described by a label, never read
# --------------------------------------------------------------------------- #


def test_m1_environment_values_do_not_reach_the_report(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The report has a row for the process-environment layer, so this is the
    place a read of ``os.environ`` would show up. The canary is set under the
    names the project reads and under an arbitrary one."""
    for name in ("OMNIAGENT_MODEL", "OMNIAGENT_BASE_URL", "OMNIAGENT_API_KEY", "CANARY_PROBE"):
        monkeypatch.setenv(name, ENV_CANARY)

    report = run_tool("inspect_config_precedence", "config.py")

    assert POSITIVE_CONTROL in report
    assert "'environment' (process environment)" in report
    assert ENV_CANARY not in report


# --------------------------------------------------------------------------- #
# M2 - only layer rows, never the rest of the file
# --------------------------------------------------------------------------- #


def test_m2_source_outside_the_layer_rows_does_not_reach_the_report(
    workspace: Workspace,
) -> None:
    """A constant, a comment and another function's body sit in the same file as
    the resolver. The report may describe the resolver and nothing else."""
    report = run_tool("inspect_config_precedence", "config.py")

    assert POSITIVE_CONTROL in report
    for canary in (CONST_CANARY, COMMENT_CANARY, BODY_CANARY):
        assert canary not in report, canary


# --------------------------------------------------------------------------- #
# M3 - one file opened
# --------------------------------------------------------------------------- #


def _record_opens(monkeypatch: pytest.MonkeyPatch, root: Path) -> list[Path]:
    """Record every path under ``root`` opened through ``Path`` or ``open``."""
    opened: list[Path] = []
    resolved_root = root.resolve()

    def note(candidate: object) -> None:
        if isinstance(candidate, str | os.PathLike):
            path = Path(candidate).resolve()
            if resolved_root in (path, *path.parents):
                opened.append(path)

    def wrap_method(name: str) -> None:
        original: Callable[..., Any] = getattr(Path, name)

        def spy(self: Path, *args: Any, **kwargs: Any) -> Any:
            note(self)
            return original(self, *args, **kwargs)

        monkeypatch.setattr(Path, name, spy)

    for method in ("read_bytes", "read_text", "open"):
        wrap_method(method)

    real_open = builtins.open

    def spy_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        note(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy_open)
    return opened


def test_m3_only_the_named_file_is_opened(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``sibling.py`` and ``notes.txt`` are in the same workspace and carry a
    canary. The tool opens ``config.py`` and nothing else."""
    opened = _record_opens(monkeypatch, workspace.root)

    report = run_tool("inspect_config_precedence", "config.py")

    assert POSITIVE_CONTROL in report
    assert opened, "the recorder saw no open at all, so it proves nothing"
    assert {path.name for path in opened} == {"config.py"}
    assert SIBLING_CANARY not in report


def test_m3_the_recorder_does_see_a_second_file_when_one_is_read(
    workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control for the test above: the same recorder catches a sibling read."""
    opened = _record_opens(monkeypatch, workspace.root)

    run_tool("inspect_config_precedence", "config.py")
    workspace.read_text("sibling.py")

    assert {path.name for path in opened} == {"config.py", "sibling.py"}


# --------------------------------------------------------------------------- #
# M4 - the error path
# --------------------------------------------------------------------------- #

#: The report is capped at 2,400 characters (``_MAX_CONFIG_PRECEDENCE_OUTPUT_CHARS``).
#: An error is the other thing the tool returns, so the same bound is the claim.
REPORT_LIMIT = 2_400


def test_m4_an_error_about_the_source_is_bounded_like_the_report(
    workspace: Workspace,
) -> None:
    long_name = "CANARY_CALL_" + "x" * 5_000
    source = f"def resolve():\n    {long_name}()\n"
    (workspace.root / "hostile.py").write_text(source, encoding="utf-8")

    result = run_tool("inspect_config_precedence", "hostile.py")

    assert result.startswith("Error:")
    assert len(result) <= REPORT_LIMIT
    # The cause, not only the size: the name is cut at the 200-character label
    # limit and says so, and the whole name is not in the result.
    assert f"unsupported call in resolve(): {long_name[:200]}...(truncated)" in result
    assert long_name not in result
