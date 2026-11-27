"""The CI workflow keeps running on the integration branch (brief 56).

The workflow names the integration branch by hand in two places. If that branch is renamed, or
one list is edited and the other not, CI stops running on the line that holds the code and
nothing fails. This test fails instead. It also pins the two jobs and the read-only token.

PyYAML is not in the ``[dev]`` extra and a dependency is not worth adding for one file, so
``read_workflow`` is a small reader bound to THIS file's shape: two-space indentation, inline
``branches: [a, b]`` lists, a ``permissions`` block of plain ``key: value`` lines. If the file
is reshaped (block-style lists, anchors, a flow-style mapping) the reader raises and the test
fails loudly; it never passes by finding nothing.

Static: reads one file, no network, no git.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
WORKFLOW = PROJECT / ".github" / "workflows" / "ci.yml"

#: The one place the branch name is written in this test.
INTEGRATION_BRANCH = "integration/canonical-20261122"
EXPECTED_JOBS = {"gates", "windows-tests"}


def _block(lines: list[str], header: str, indent: int) -> list[str]:
    """The lines indented deeper than ``header`` under it (header is at ``indent``)."""
    start = next(
        (index for index, line in enumerate(lines) if line == " " * indent + header + ":"), None
    )
    if start is None:
        raise AssertionError(f"ci.yml has no '{header}:' at indent {indent}; shape-bound reader")
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return body


def read_workflow(text: str) -> dict[str, object]:
    lines = [line.split(" #")[0].rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    triggers = _block(lines, "on", 0)
    branches: dict[str, list[str]] = {}
    for event in ("push", "pull_request"):
        match = [
            re.fullmatch(r"\s{4}branches: \[(.*)\]", line)
            for line in _block(triggers, event, 2)
            if line.strip().startswith("branches:")
        ]
        if len(match) != 1 or match[0] is None:
            raise AssertionError(f"ci.yml '{event}' has no single inline 'branches: [..]' line")
        branches[event] = [name.strip() for name in match[0].group(1).split(",") if name.strip()]
    names = _block(lines, "jobs", 0)
    jobs = {line.strip()[:-1] for line in names if re.fullmatch(r"  [\w-]+:", line)}
    permissions = {
        key.strip(): value.strip()
        for key, _, value in (line.partition(":") for line in _block(lines, "permissions", 0))
        if key.strip()
    }
    return {"branches": branches, "jobs": jobs, "permissions": permissions}


def current() -> dict[str, object]:
    return read_workflow(WORKFLOW.read_text(encoding="utf-8"))


def mutated(old: str, new: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(old) >= 1, f"{old!r} is not in ci.yml; the test below would prove nothing"
    return text.replace(old, new, 1)


def lists(workflow: dict[str, object]) -> dict[str, list[str]]:
    return workflow["branches"]  # type: ignore[return-value]


def test_both_triggers_run_on_main_and_the_integration_branch() -> None:
    for event, names in lists(current()).items():
        assert {"main", INTEGRATION_BRANCH} <= set(names), f"{event} lacks main or integration"


def test_the_two_trigger_lists_are_the_same() -> None:
    triggers = lists(current())

    assert sorted(triggers["push"]) == sorted(triggers["pull_request"])


def test_the_two_jobs_are_still_defined() -> None:
    assert current()["jobs"] == EXPECTED_JOBS


def test_the_token_stays_read_only() -> None:
    assert current()["permissions"] == {"contents": "read"}


def test_the_reader_sees_a_missing_integration_branch() -> None:
    workflow = read_workflow(mutated("[main, " + INTEGRATION_BRANCH + "]", "[main]"))

    assert INTEGRATION_BRANCH not in lists(workflow)["push"]
    assert INTEGRATION_BRANCH in lists(workflow)["pull_request"]


def test_the_reader_sees_two_lists_that_differ() -> None:
    text = mutated("[main, " + INTEGRATION_BRANCH + "]", "[main, other]")
    triggers = lists(read_workflow(text))

    assert sorted(triggers["push"]) != sorted(triggers["pull_request"])


def test_the_reader_sees_a_widened_token() -> None:
    assert read_workflow(mutated("contents: read", "contents: write"))["permissions"] == {
        "contents": "write"
    }
    assert read_workflow(mutated("contents: read", "contents: read\n  id-token: write"))[
        "permissions"
    ] == {"contents": "read", "id-token": "write"}


def test_the_reader_sees_a_missing_job() -> None:
    assert read_workflow(mutated("  windows-tests:", "  windows-renamed:"))["jobs"] != EXPECTED_JOBS


def test_a_reshaped_file_fails_loudly_instead_of_passing() -> None:
    reshaped = mutated("branches: [main, " + INTEGRATION_BRANCH + "]", "branches:\n      - main")

    with pytest.raises(AssertionError, match=r"shape-bound|inline"):
        read_workflow(reshaped)
