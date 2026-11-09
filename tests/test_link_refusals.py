"""Search must prune links that lead outside the workspace."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from sandbox import Workspace, get_workspace, set_workspace
from tools import search_text


def _make_windows_junction(link: Path, target: Path) -> None:
    def quote(value: Path) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    command = (
        "$ErrorActionPreference = 'Stop'; "
        f"New-Item -ItemType Junction -Path {quote(link)} "
        f"-Target {quote(target)} | Out-Null"
    )
    powershell = (
        Path(os.environ["SYSTEMROOT"])
        / "System32"
        / "WindowsPowerShell"
        / "v1.0"
        / "powershell.exe"
    )
    result = subprocess.run(  # noqa: S603 - fixed executable; temp paths are PowerShell-quoted
        [str(powershell), "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        check=False,
        text=True,
    )
    assert result.returncode == 0, (
        "Could not build the mandatory Windows junction fixture with New-Item: "
        f"{result.stdout.strip()} {result.stderr.strip()}"
    )
    assert link.is_dir(), "junction creation returned success but the junction is absent"


def _make_symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip(
                "Windows symlink privilege SeCreateSymbolicLinkPrivilege is missing "
                "and Developer Mode does not permit unprivileged symlink creation "
                f"(WinError 1314: {exc})"
            )
        pytest.fail(f"Could not build the required symlink fixture: {exc}")


def _assert_external_link_is_pruned(
    tmp_path: Path,
    link_builder: Callable[[Path, Path], None],
) -> None:
    outside_marker = f"outside-marker-{tmp_path.name}"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text(outside_marker + "\n", encoding="utf-8")

    root = tmp_path / "workspace"
    inside = root / "inside"
    inside.mkdir(parents=True)
    inside_file = inside / "ordinary.txt"
    inside_file.write_text("inside-walk-marker\n", encoding="utf-8")

    link = root / "jump"
    link_builder(link, outside)

    previous_workspace = get_workspace()
    set_workspace(Workspace.at(root))
    try:
        outside_result = search_text(outside_marker)
        absent_result = search_text(f"absent-marker-{tmp_path.name}")
        inside_result = search_text("inside-walk-marker")
        inside_file.write_text(
            f"inside-walk-marker\n{outside_marker}\n", encoding="utf-8"
        )
        marker_collision_result = search_text(outside_marker)
        collision_absent_result = search_text(f"still-absent-{tmp_path.name}")
    finally:
        set_workspace(previous_workspace)

    # Ma: the external marker has no in-workspace source and must not match.
    assert outside_result.startswith("No match")
    assert "jump/secret.txt" not in outside_result
    assert absent_result.startswith("No match")
    assert "(1 files searched)" in absent_result
    assert "inside/ordinary.txt:1: inside-walk-marker" in inside_result

    # Mb: when the same marker is also inside, only that real path may match.
    assert f"inside/ordinary.txt:2: {outside_marker}" in marker_collision_result
    assert "jump/secret.txt" not in marker_collision_result
    assert collision_absent_result.startswith("No match")
    assert "(1 files searched)" in collision_absent_result


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions do not apply on POSIX")
def test_search_prunes_a_windows_junction(tmp_path: Path) -> None:
    _assert_external_link_is_pruned(tmp_path, _make_windows_junction)


def test_search_prunes_an_external_symlink(tmp_path: Path) -> None:
    _assert_external_link_is_pruned(tmp_path, _make_symlink)
