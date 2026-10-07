"""Tests for putting a dataset somewhere it can be trained from.

The destination is a removable exFAT volume, so a copy that silently differs
from its source is the failure worth engineering against: a dataset is only
worth training on if what arrived is what was collected.

The other thing asserted here is that provenance cannot go missing. A dataset
that cannot say what prompt and which teacher it was collected under is not a
dataset you can reproduce, and `dataset_provenance` already refuses to treat a
missing sidecar as agreement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from publish_dataset import PublishError, publish, verify

from dataset_provenance import write_sidecar


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    """A two-example dataset with its provenance sidecar beside it."""
    path = tmp_path / "source" / "dataset.jsonl"
    path.parent.mkdir()
    path.write_text(
        json.dumps({"messages": [{"role": "user", "content": "hi"}]}) + "\n"
        + json.dumps({"messages": [{"role": "user", "content": "again"}]}) + "\n",
        encoding="utf-8",
    )
    write_sidecar(path)
    return path


def test_the_dataset_and_its_sidecar_both_arrive(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"

    publish(dataset, dest, teacher="qwen2.5-coder:7b")

    assert (dest / "dataset.jsonl").read_text("utf-8") == dataset.read_text("utf-8")
    assert (dest / "dataset.jsonl.provenance.json").is_file()


def test_a_dataset_without_provenance_is_refused(tmp_path: Path) -> None:
    """A missing sidecar is not agreement; it is an unanswered question."""
    orphan = tmp_path / "orphan.jsonl"
    orphan.write_text(json.dumps({"messages": []}) + "\n", encoding="utf-8")

    with pytest.raises(PublishError, match="provenance"):
        publish(orphan, tmp_path / "drive", teacher="qwen2.5-coder:7b")


def test_extra_files_travel_with_it(dataset: Path, tmp_path: Path) -> None:
    """The raw log is the source of truth and has to arrive too."""
    raw = dataset.parent / "collect.jsonl"
    raw.write_text('{"event": "agent.turn.start"}\n', encoding="utf-8")
    dest = tmp_path / "drive"

    publish(dataset, dest, teacher="t", extras=(raw,))

    assert (dest / "collect.jsonl").is_file()


def test_the_manifest_records_what_the_sidecar_cannot(dataset: Path, tmp_path: Path) -> None:
    """The gap this closes: the sidecar names the prompt and nothing else.

    Which teacher produced the trajectories, and which workspace rule the
    agent ran under, both change the data and neither is in the sidecar.
    """
    dest = tmp_path / "drive"

    manifest = publish(dataset, dest, teacher="qwen2.5-coder:7b", workspace_rule="sealed")

    assert manifest["teacher_model"] == "qwen2.5-coder:7b"
    assert manifest["workspace_rule"] == "sealed"
    assert manifest["examples"] == 2
    assert manifest["system_prompt_sha256"]
    written = json.loads((dest / "MANIFEST.json").read_text("utf-8"))
    assert written == manifest


def test_every_published_file_is_listed_with_its_digest(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"

    publish(dataset, dest, teacher="t")

    sums = (dest / "SHA256SUMS").read_text("utf-8").split("\n")
    listed = {line.split("  ")[1] for line in sums if line.strip()}
    assert "dataset.jsonl" in listed
    assert "dataset.jsonl.provenance.json" in listed


def test_verify_passes_on_an_untouched_destination(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")

    assert verify(dest) == []


def test_verify_names_a_file_that_changed_after_the_copy(
    dataset: Path, tmp_path: Path
) -> None:
    """The reason this is a script and not a copy command.

    A removable volume can hand back something other than what was written,
    and a dataset is only worth training on if what arrived is what was
    collected.
    """
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    (dest / "dataset.jsonl").write_text("tampered\n", encoding="utf-8")

    assert verify(dest) == ["dataset.jsonl"]


def test_verify_names_a_file_that_went_missing(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    (dest / "dataset.jsonl.provenance.json").unlink()

    assert verify(dest) == ["dataset.jsonl.provenance.json"]


def test_publishing_twice_to_the_same_place_is_not_an_error(
    dataset: Path, tmp_path: Path
) -> None:
    """A re-run after a half-finished copy has to be allowed to finish it."""
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")

    publish(dataset, dest, teacher="t")

    assert verify(dest) == []


def test_a_copy_that_arrives_different_fails_the_publish(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard no other test here reaches: corruption during the copy.

    verify() covers a file that changed afterwards. This covers the write
    itself coming back wrong, which on a removable volume is the case worth
    failing loudly on rather than discovering during training.
    """
    def truncating_copy(src: object, dst: Path | str) -> None:
        Path(dst).write_text("half a fi", encoding="utf-8")

    monkeypatch.setattr("publish_dataset.shutil.copy2", truncating_copy)

    with pytest.raises(PublishError, match="does not match the source"):
        publish(dataset, tmp_path / "drive", teacher="t")
