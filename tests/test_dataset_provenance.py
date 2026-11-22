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

import dataset_limits
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


def test_provenance_refuses_an_over_limit_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_BYTES", 32)
    dataset = tmp_path / "too-large.jsonl"
    dataset.write_bytes(b" " * 33)

    with pytest.raises(ProvenanceError, match="maximum file size"):
        dataset_fingerprint(dataset)


def test_provenance_refuses_an_overlong_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_LINE_BYTES", 16)
    dataset = tmp_path / "long-record.jsonl"
    dataset.write_bytes(b" " * 17 + b"\n")

    with pytest.raises(ProvenanceError, match="maximum line size"):
        dataset_fingerprint(dataset)


def test_provenance_refuses_too_many_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_EXAMPLES", 1)
    dataset = tmp_path / "too-many.jsonl"
    dataset.write_text(_example("PROMPT A") + "\n" + _example("PROMPT A") + "\n", "utf-8")

    with pytest.raises(ProvenanceError, match="maximum record count"):
        dataset_fingerprint(dataset)


def test_provenance_refuses_too_many_physical_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(dataset_limits, "MAX_DATASET_LINES", 2)
    dataset = tmp_path / "too-many-lines.jsonl"
    dataset.write_bytes(b"\n\n\n")

    with pytest.raises(ProvenanceError, match="maximum physical line count"):
        dataset_fingerprint(dataset)


def test_provenance_refuses_deeply_nested_json(tmp_path: Path) -> None:
    dataset = tmp_path / "deep.jsonl"
    dataset.write_text("[" * 5_000 + "]" * 5_000 + "\n", encoding="utf-8")

    with pytest.raises(ProvenanceError, match=r"JSON nesting.*too deep"):
        dataset_fingerprint(dataset)


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


# --------------------------------------------------------------------------- #
# hostile shapes: every one is a ProvenanceError, never a traceback
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"[1, 2]\n", "is not an object"),
        (b'"text"\n', "is not an object"),
        (b"{not json}\n", "is not valid JSON"),
        (b"\xff\xfe\n", "is not valid UTF-8"),
        (b'{"messages": 5}\n', "has no system turn"),
        (b'{"messages": [1, "x"]}\n', "has no system turn"),
        (b'{"messages": [{"role": "user", "content": "hi"}]}\n', "has no system turn"),
        (b'{"messages": [{"role": "system", "content": 7}]}\n', "invalid system turn"),
        (b"[" * 5000 + b"]" * 5000 + b"\n", "nesting that is too deep"),
    ],
    ids=[
        "array-line",
        "string-line",
        "bad-json",
        "bad-utf8",
        "messages-not-a-list",
        "messages-not-objects",
        "no-system-turn",
        "system-content-not-a-string",
        "deep-nesting",
    ],
)
def test_a_malformed_dataset_line_is_a_provenance_error(
    tmp_path: Path, raw: bytes, expected: str
) -> None:
    dataset = tmp_path / "hostile.jsonl"
    dataset.write_bytes(raw)

    with pytest.raises(ProvenanceError, match=expected):
        dataset_fingerprint(dataset)


def test_the_brackets_inside_a_string_are_not_nesting(tmp_path: Path) -> None:
    dataset = tmp_path / "strings.jsonl"
    prompt = "[" * 500 + '\\" ' + "{" * 500
    dataset.write_text(_example(prompt) + "\n", "utf-8")

    assert dataset_fingerprint(dataset) == sha256(prompt.encode("utf-8")).hexdigest()


def test_a_missing_dataset_is_a_provenance_error(tmp_path: Path) -> None:
    with pytest.raises(ProvenanceError, match="could not read"):
        dataset_fingerprint(tmp_path / "absent.jsonl")


def _sidecar_for(tmp_path: Path, raw: bytes) -> Path:
    dataset = tmp_path / "d.jsonl"
    dataset.write_text(_example("P") + "\n", "utf-8")
    (tmp_path / "d.jsonl.provenance.json").write_bytes(raw)
    return dataset


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"[1]", "must contain a JSON object"),
        (b'"text"', "must contain a JSON object"),
        (b"{broken", "invalid provenance sidecar"),
        (b"\xff", "invalid provenance sidecar"),
        (b"[" * 5000 + b"]" * 5000, "nesting is too deep"),
        (b"x" * (dataset_limits.MAX_SIDECAR_BYTES + 1), "exceeds maximum size"),
    ],
    ids=["array", "string", "broken", "bad-utf8", "deep", "oversized"],
)
def test_a_malformed_sidecar_is_a_provenance_error(
    tmp_path: Path, raw: bytes, expected: str
) -> None:
    with pytest.raises(ProvenanceError, match=expected):
        read_sidecar(_sidecar_for(tmp_path, raw))


def test_a_sidecar_at_the_size_limit_is_read(tmp_path: Path) -> None:
    body = b'{"pad": "'
    tail = b'"}'
    padding = b"x" * (dataset_limits.MAX_SIDECAR_BYTES - len(body) - len(tail))
    raw = body + padding + tail
    assert len(raw) == dataset_limits.MAX_SIDECAR_BYTES

    assert read_sidecar(_sidecar_for(tmp_path, raw))["pad"] == padding.decode()


def test_two_prompts_in_one_line_are_still_a_mixed_dataset(tmp_path: Path) -> None:
    messages = [
        {"role": "system", "content": "ONE"},
        {"role": "system", "content": "TWO"},
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a"},
    ]
    dataset = tmp_path / "mixed.jsonl"
    dataset.write_text(json.dumps({"messages": messages}) + "\n", "utf-8")

    with pytest.raises(ProvenanceError, match="mixes 2 distinct"):
        dataset_fingerprint(dataset)
