"""Build and import the wheel without changing the checkout or global environment."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_installed_wheel_includes_dataset_provenance(tmp_path: Path) -> None:
    if any(importlib.util.find_spec(name) is None for name in ("setuptools", "wheel")):
        pytest.skip("setuptools/wheel build tools are unavailable in this environment")

    source = tmp_path / "source"
    source.mkdir()
    shutil.copy2(REPO_ROOT / "pyproject.toml", source / "pyproject.toml")
    shutil.copy2(REPO_ROOT / "README.md", source / "README.md")
    shutil.copy2(REPO_ROOT / "LICENSE", source / "LICENSE")

    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    modules = project["tool"]["setuptools"]["py-modules"]
    assert "dataset_provenance" in modules
    for module in modules:
        shutil.copy2(REPO_ROOT / f"{module}.py", source / f"{module}.py")

    wheel_dir = tmp_path / "wheel"
    install_dir = tmp_path / "install"
    runner_dir = tmp_path / "runner"
    for directory in (wheel_dir, install_dir, runner_dir):
        directory.mkdir()

    subprocess.run(  # noqa: S603 - fixed Python/pip commands and temporary local paths
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(source),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(wheel_dir.glob("omniagent-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_members = archive.namelist()
    assert "dataset_provenance.py" in wheel_members
    assert not any(
        Path(member).name.lower() in {"agents.md", "codex.md", "next_chat.md"}
        for member in wheel_members
    )

    subprocess.run(  # noqa: S603 - installs only the wheel built above into temp storage
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_dir),
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(install_dir)
    log_path = runner_dir / "fixture.jsonl"
    prompt = "You are a fixture agent."
    records = [
        {"event": "agent.created", "session_id": "fixture", "system_prompt": prompt},
        {
            "event": "agent.turn.start",
            "session_id": "fixture",
            "turn": 1,
            "question": "How much is two plus two?",
        },
        {
            "event": "agent.llm.response",
            "session_id": "fixture",
            "turn": 1,
            "step": 1,
            "reply": "Thought: calculate.\nAction: calculate\nAction Input: 2 + 2",
        },
        {
            "event": "agent.tool.result",
            "session_id": "fixture",
            "turn": 1,
            "step": 1,
            "ok": True,
            "observation": "2 + 2 = 4",
        },
        {
            "event": "agent.llm.response",
            "session_id": "fixture",
            "turn": 1,
            "step": 2,
            "reply": "Thought: done.\nFinal Answer: 4",
        },
        {
            "event": "agent.turn.end",
            "session_id": "fixture",
            "turn": 1,
            "answer": "4",
        },
    ]
    log_path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    dataset_path = runner_dir / "fixture-dataset.jsonl"
    runner_code = "; ".join(
        [
            "import export_dataset, dataset_provenance, sys",
            "print(export_dataset.__file__)",
            "print(dataset_provenance.__file__)",
            "raise SystemExit(export_dataset.main(sys.argv[1:]))",
        ]
    )
    result = subprocess.run(  # noqa: S603 - executes the installed local wheel with fixed args
        [
            sys.executable,
            "-c",
            runner_code,
            str(log_path),
            "--output",
            str(dataset_path),
            "--stats",
        ],
        cwd=runner_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert str(install_dir) in result.stdout
    assert dataset_path.is_file()
    assert dataset_path.with_name(dataset_path.name + ".provenance.json").is_file()
