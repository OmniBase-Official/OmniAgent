"""Tests for the directory a training run keeps to itself.

`models/runs/` was one directory for every run and
`models/<name>-manifest.json` was one file, so each training overwrote the
record of the one before it. That is why `models/runs/` looked empty of
history while two fine-tunes existed.

The manifest's required fields are enforced rather than documented: a manifest
that cannot say which base model, how many examples or which strategy produced
a model is not a record of anything, and the failure should happen when it is
written rather than when someone reads it back a month later.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from run_dir import new_run_dir, write_manifest

# tzinfo because ruff DTZ001 refuses a naive datetime, and the generator passes
# an aware one; the plan's snippet omitted it.
WHEN = datetime(2026, 10, 6, 7, 30, 0, tzinfo=UTC)
REQUIRED = {"base_model": "Qwen/Qwen2.5-1.5B-Instruct", "examples": 153, "strategy": "qlora-4bit"}


def test_a_run_directory_is_named_for_its_timestamp(tmp_path: Path) -> None:
    run = new_run_dir(tmp_path, WHEN)

    assert run.name == "20261006T073000"
    assert run.is_dir()


def test_two_runs_in_the_same_second_do_not_collide(tmp_path: Path) -> None:
    first, second = new_run_dir(tmp_path, WHEN), new_run_dir(tmp_path, WHEN)

    assert first != second
    assert second.name.endswith("-2")


def test_a_third_run_in_the_same_second_keeps_counting(tmp_path: Path) -> None:
    for _ in range(2):
        new_run_dir(tmp_path, WHEN)

    assert new_run_dir(tmp_path, WHEN).name.endswith("-3")


def test_a_manifest_without_the_required_fields_is_refused(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        write_manifest(new_run_dir(tmp_path, WHEN), {"examples": 109})


def test_the_manifest_is_written_inside_the_run(tmp_path: Path) -> None:
    run = new_run_dir(tmp_path, WHEN)

    path = write_manifest(run, REQUIRED)

    assert path == run / "manifest.json"
    assert json.loads(path.read_text("utf-8"))["examples"] == 153


def test_the_manifest_keeps_the_fields_it_was_given(tmp_path: Path) -> None:
    run = new_run_dir(tmp_path, WHEN)

    written = json.loads(write_manifest(run, {**REQUIRED, "final_loss": 0.4586}).read_text("utf-8"))

    assert written["base_model"] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert written["strategy"] == "qlora-4bit"
    assert written["final_loss"] == 0.4586


def test_the_manifest_records_which_run_it_belongs_to(tmp_path: Path) -> None:
    """Otherwise a manifest copied to the flat path cannot say where it came from."""
    run = new_run_dir(tmp_path, WHEN)

    written = json.loads(write_manifest(run, REQUIRED).read_text("utf-8"))

    assert written["run"] == "20261006T073000"
