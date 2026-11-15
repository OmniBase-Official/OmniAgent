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

import dataset_provenance as provenance
import validate_dataset
from agent import AgentConfig, ReActAgent
from dataset_provenance import (
    ProvenanceError,
    dataset_fingerprint,
    prompt_fingerprint,
    read_sidecar,
    render_system_prompt,
    write_sidecar,
)
from export_dataset import Turn, build_examples
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


def test_provenance_caps_match_the_dataset_validator() -> None:
    assert provenance.MAX_DATASET_BYTES == validate_dataset.MAX_DATASET_BYTES
    assert provenance.MAX_DATASET_LINE_BYTES == validate_dataset.MAX_DATASET_LINE_BYTES
    assert provenance.MAX_DATASET_LINES == validate_dataset.MAX_DATASET_LINES
    assert provenance.MAX_DATASET_EXAMPLES == validate_dataset.MAX_DATASET_EXAMPLES
    assert provenance.MAX_JSON_NESTING == validate_dataset.MAX_JSON_NESTING


def test_line_and_record_count_limits_are_enforced_before_sidecar_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blank_lines = tmp_path / "many-lines.jsonl"
    blank_lines.write_text("\n\n", encoding="utf-8")
    monkeypatch.setattr(provenance, "MAX_DATASET_LINES", 1)
    with pytest.raises(ProvenanceError, match="line limit"):
        write_sidecar(blank_lines)
    assert not provenance.sidecar_path(blank_lines).exists()

    records = tmp_path / "many-records.jsonl"
    row = _example("PROMPT A")
    records.write_text(row + "\n" + row + "\n", encoding="utf-8")
    monkeypatch.setattr(provenance, "MAX_DATASET_LINES", 10)
    monkeypatch.setattr(provenance, "MAX_DATASET_EXAMPLES", 1)
    with pytest.raises(ProvenanceError, match="record limit"):
        write_sidecar(records)
    assert not provenance.sidecar_path(records).exists()


def test_an_oversized_dataset_is_rejected_before_sidecar_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "large.jsonl"
    dataset.write_bytes(b"x" * 33)
    monkeypatch.setattr(provenance, "MAX_DATASET_BYTES", 32)

    with pytest.raises(ProvenanceError, match="dataset limit"):
        write_sidecar(dataset)

    assert not provenance.sidecar_path(dataset).exists()


def test_a_giant_line_is_rejected_before_sidecar_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "wide.jsonl"
    dataset.write_bytes(b" " * 17)
    monkeypatch.setattr(provenance, "MAX_DATASET_BYTES", 128)
    monkeypatch.setattr(provenance, "MAX_DATASET_LINE_BYTES", 16)

    with pytest.raises(ProvenanceError, match="line limit"):
        write_sidecar(dataset)

    assert not provenance.sidecar_path(dataset).exists()


def test_deep_json_is_rejected_before_sidecar_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "deep.jsonl"
    row = json.loads(_example("PROMPT A"))
    row["extra"] = [[[[[]]]]]
    dataset.write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr(provenance, "MAX_JSON_NESTING", 4)

    with pytest.raises(ProvenanceError, match="nesting limit"):
        write_sidecar(dataset)

    assert not provenance.sidecar_path(dataset).exists()


def test_malformed_later_row_does_not_mutate_existing_sidecar(tmp_path: Path) -> None:
    dataset = tmp_path / "malformed.jsonl"
    dataset.write_text(_example("PROMPT A") + "\n{" + "\n", encoding="utf-8")
    sidecar = provenance.sidecar_path(dataset)
    sidecar.write_text("previous sidecar\n", encoding="utf-8")

    with pytest.raises(ProvenanceError, match="line 2 is not valid JSON"):
        write_sidecar(dataset)

    assert sidecar.read_text(encoding="utf-8") == "previous sidecar\n"
    assert list(tmp_path.glob(".*.tmp")) == []


def test_exporter_produced_dataset_gets_streamed_provenance(tmp_path: Path) -> None:
    turn = Turn(
        session_id="synthetic",
        turn=1,
        question="hi",
        answer="hello",
        exchange=[{"role": "assistant", "content": "hello"}],
    )
    examples, stats = build_examples([turn], {"synthetic": "PROMPT A"})
    dataset = tmp_path / "exported.jsonl"
    dataset.write_text(
        "".join(json.dumps(example) + "\n" for example in examples), encoding="utf-8"
    )

    assert stats.exported == 1
    assert dataset_fingerprint(dataset) == sha256(b"PROMPT A").hexdigest()
    write_sidecar(dataset)
    written = read_sidecar(dataset)
    assert written["examples"] == 1


@pytest.mark.parametrize(
    "row",
    [
        '{"messages":[],"messages":[{"role":"system","content":"PROMPT A"}]}',
        '{"messages":[{"role":"system","role":"user","content":"PROMPT A"}]}',
        (
            '{"messages":[{"role":"system","content":"PROMPT A",'
            '"content":"PROMPT B"}]}'
        ),
    ],
    ids=["top-level-messages", "nested-role", "nested-content"],
)
def test_duplicate_json_keys_are_refused_without_changing_sidecar(
    tmp_path: Path, row: str
) -> None:
    dataset = tmp_path / "ambiguous.jsonl"
    dataset.write_text(row + "\n", encoding="utf-8")
    sidecar = provenance.sidecar_path(dataset)
    sidecar.write_text("previous sidecar\n", encoding="utf-8")

    with pytest.raises(ProvenanceError, match="duplicate object key") as caught:
        dataset_fingerprint(dataset)
    assert "PROMPT A" not in str(caught.value)
    assert "PROMPT B" not in str(caught.value)

    with pytest.raises(ProvenanceError, match="duplicate object key") as caught:
        write_sidecar(dataset)
    assert "PROMPT A" not in str(caught.value)
    assert "PROMPT B" not in str(caught.value)
    assert sidecar.read_text(encoding="utf-8") == "previous sidecar\n"
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize(
    "row",
    [
        (
            '{"messages":[{"role":"system","content":"PROMPT A"},'
            '{"role":"user","content":"hi"},'
            '{"role":"assistant","content":"hello"}],"extra":"PRIVATE_VALUE"}'
        ),
        (
            '{"messages":[{"role":"system","content":"PROMPT A"},'
            '{"role":"user","content":"hi","extra":"PRIVATE_VALUE"},'
            '{"role":"assistant","content":"hello"}]}'
        ),
        (
            '{"messages":[{"role":"system","content":"PROMPT A"},'
            '{"role":"other","content":"hi"},'
            '{"role":"assistant","content":"hello"}]}'
        ),
        (
            '{"messages":[{"role":"system","content":"PROMPT A"},'
            '{"role":"user","content":"  "},'
            '{"role":"assistant","content":"hello"}]}'
        ),
        (
            '{"messages":[{"role":"system","content":"  "},'
            '{"role":"user","content":"hi"},'
            '{"role":"assistant","content":"hello"}]}'
        ),
    ],
    ids=[
        "unexpected-top-level-field",
        "unexpected-message-field",
        "unsupported-role",
        "blank-message-content",
        "blank-system-prompt",
    ],
)
def test_schema_invalid_rows_are_refused_without_changing_sidecar(
    tmp_path: Path, row: str
) -> None:
    dataset = tmp_path / "invalid-schema.jsonl"
    dataset.write_text(row + "\n", encoding="utf-8")
    sidecar = provenance.sidecar_path(dataset)
    sidecar.write_text("previous sidecar\n", encoding="utf-8")

    with pytest.raises(ProvenanceError, match=r"invalid|unsupported|exported") as caught:
        dataset_fingerprint(dataset)
    assert "PRIVATE_VALUE" not in str(caught.value)

    with pytest.raises(ProvenanceError, match=r"invalid|unsupported|exported") as caught:
        write_sidecar(dataset)
    assert "PRIVATE_VALUE" not in str(caught.value)
    assert sidecar.read_text(encoding="utf-8") == "previous sidecar\n"
    assert list(tmp_path.glob(".*.tmp")) == []


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-key",
        "extra-key",
        "example-count-type",
        "example-count-zero",
        "dataset-identity",
        "system-digest",
        "live-digest",
        "match-consistency",
    ],
)
def test_read_sidecar_rejects_invalid_schema(
    tmp_path: Path, mutation: str
) -> None:
    dataset = tmp_path / "schema.jsonl"
    dataset.write_text(_example(render_system_prompt()) + "\n", encoding="utf-8")
    sidecar = write_sidecar(dataset)
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    if mutation == "missing-key":
        del payload["matches_live_prompt"]
    elif mutation == "extra-key":
        payload["extra"] = "PRIVATE_VALUE"
    elif mutation == "example-count-type":
        payload["examples"] = True
    elif mutation == "example-count-zero":
        payload["examples"] = 0
    elif mutation == "dataset-identity":
        payload["dataset"] = "different.jsonl"
    elif mutation == "system-digest":
        payload["system_prompt_sha256"] = "not-a-sha256"
    elif mutation == "live-digest":
        payload["live_prompt_sha256"] = "g" * 64
    else:
        payload["matches_live_prompt"] = not payload["matches_live_prompt"]
    sidecar.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProvenanceError):
        read_sidecar(dataset)


def test_read_sidecar_rejects_symlink(tmp_path: Path) -> None:
    dataset = tmp_path / "linked.jsonl"
    dataset.write_text(_example(render_system_prompt()) + "\n", encoding="utf-8")
    sidecar = write_sidecar(dataset)
    external = tmp_path / "external-provenance.json"
    external.write_bytes(sidecar.read_bytes())
    sidecar.unlink()
    try:
        sidecar.symlink_to(external)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    with pytest.raises(ProvenanceError, match="regular non-link"):
        read_sidecar(dataset)
