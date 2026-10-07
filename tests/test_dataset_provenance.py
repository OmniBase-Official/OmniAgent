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
    dataset_fingerprint,
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
    dataset.write_text(_example(render_system_prompt()) + "\n", encoding="utf-8")

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
    dataset.write_text(_example(render_system_prompt()) + "\n", encoding="utf-8")

    path = write_sidecar(dataset)

    assert path == tmp_path / "dataset.jsonl.provenance.json"
    assert json.loads(path.read_text(encoding="utf-8"))["examples"] == 1


def test_an_empty_dataset_cannot_be_given_provenance(tmp_path: Path) -> None:
    """It used to get a sidecar saying nothing, which is worse than refusing.

    This test replaces one that asserted `examples == 0` on an empty file:
    stamping a prompt fingerprint onto a dataset with no examples records a
    claim about data that is not there. An empty dataset is not trainable
    either way -- `validate_dataset` has `min_examples`.
    """
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("", encoding="utf-8")

    with pytest.raises(ProvenanceError, match="empty"):
        write_sidecar(dataset)


# --------------------------------------------------------------------------- #
# the fingerprint the data itself carries
# --------------------------------------------------------------------------- #


def _example(system: str, user: str = "hi") -> str:
    return json.dumps(
        {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
                {"role": "assistant", "content": "Final Answer: hello"},
            ]
        }
    )


def test_the_fingerprint_is_read_out_of_the_dataset(tmp_path: Path) -> None:
    """Every example carries its system prompt verbatim, so it can be hashed.

    This is the difference between a measurement and a claim. Hashing the
    prompt the code renders today says what the environment is; hashing the
    prompt inside the file says what the data is.
    """
    dataset = tmp_path / "d.jsonl"
    dataset.write_text(_example("PROMPT A") + "\n" + _example("PROMPT A") + "\n", "utf-8")

    assert dataset_fingerprint(dataset) == sha256(b"PROMPT A").hexdigest()


def test_a_dataset_mixing_two_prompts_is_refused(tmp_path: Path) -> None:
    """Pooling two collections produces data true of neither prompt."""
    dataset = tmp_path / "d.jsonl"
    dataset.write_text(_example("PROMPT A") + "\n" + _example("PROMPT B") + "\n", "utf-8")

    with pytest.raises(ProvenanceError, match="mixes 2 distinct"):
        dataset_fingerprint(dataset)


def test_an_example_without_a_system_turn_is_refused(tmp_path: Path) -> None:
    dataset = tmp_path / "d.jsonl"
    no_system = json.dumps({"messages": [{"role": "user", "content": "hi"}]})
    dataset.write_text(no_system + "\n", "utf-8")

    with pytest.raises(ProvenanceError, match="no system"):
        dataset_fingerprint(dataset)


def test_the_sidecar_records_the_datasets_own_prompt_not_todays(tmp_path: Path) -> None:
    """The check the module was written for, and could not previously make.

    write_sidecar hashed the prompt the code renders now, which stamps today's
    fingerprint onto a dataset of any age -- so the one thing it existed to
    detect, a dataset collected under a prompt that no longer exists, could not
    be detected by it. Measured on the real files: data/dataset.jsonl carries
    ee43a4af... in all 109 examples while the live prompt is 36397f37...
    """
    dataset = tmp_path / "old.jsonl"
    dataset.write_text(_example("A PROMPT THAT NO LONGER EXISTS") + "\n", "utf-8")

    write_sidecar(dataset)
    recorded = read_sidecar(dataset)

    assert recorded["system_prompt_sha256"] == sha256(
        b"A PROMPT THAT NO LONGER EXISTS"
    ).hexdigest()
    assert recorded["live_prompt_sha256"] == prompt_fingerprint()
    assert recorded["matches_live_prompt"] is False


def test_a_current_dataset_is_recorded_as_matching(tmp_path: Path) -> None:
    dataset = tmp_path / "now.jsonl"
    dataset.write_text(_example(render_system_prompt()) + "\n", "utf-8")

    write_sidecar(dataset)
    recorded = read_sidecar(dataset)

    assert recorded["matches_live_prompt"] is True
    assert recorded["system_prompt_sha256"] == prompt_fingerprint()
