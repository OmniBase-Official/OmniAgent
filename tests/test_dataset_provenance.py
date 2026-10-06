"""Tests for the prompt a dataset was collected under.

`read_file`'s description changed in 58bb801 and `data/dataset.jsonl` predates
it, so the served model was trained against a prompt it is no longer given.
That was found by hand. These assertions are the start of finding it by check:
the dataset records the hash the agent already logs for its own prompt, and a
dataset with no record is an error rather than a match.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from agent import AgentConfig, ReActAgent
from dataset_provenance import (
    ProvenanceError,
    prompt_fingerprint,
    read_sidecar,
    render_system_prompt,
    write_sidecar,
)
from tests.fakes import FakeOpenAI


def test_the_fingerprint_matches_the_prompt_the_agent_builds() -> None:
    """One hash, not two. The agent logs this at agent.py:467."""
    agent = ReActAgent(
        config=AgentConfig(verbose=False), client=FakeOpenAI().as_client(), printer=lambda _: None
    )

    assert render_system_prompt() == agent.system_prompt
    assert prompt_fingerprint() == sha256(agent.system_prompt.encode("utf-8")).hexdigest()


def test_a_sidecar_records_the_fingerprint_and_the_example_count(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text('{"messages": []}\n', encoding="utf-8")

    write_sidecar(dataset)
    written = read_sidecar(dataset)

    assert written["system_prompt_sha256"] == prompt_fingerprint()
    assert written["examples"] == 1


def test_a_dataset_with_no_sidecar_is_an_error_not_a_match(tmp_path: Path) -> None:
    """A missing record must not read as agreement."""
    with pytest.raises(ProvenanceError, match="no provenance"):
        read_sidecar(tmp_path / "dataset.jsonl")


def test_the_sidecar_sits_beside_the_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("", encoding="utf-8")

    path = write_sidecar(dataset)

    assert path == tmp_path / "dataset.jsonl.provenance.json"
    assert json.loads(path.read_text(encoding="utf-8"))["examples"] == 0
