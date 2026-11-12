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
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import publish_dataset
from publish_dataset import PublishError, publish, verify

from dataset_provenance import write_sidecar


def _create_junction(link: Path, target: Path) -> None:
    """Create a Windows directory junction or skip when the host cannot."""
    if os.name != "nt":
        pytest.skip("Windows directory junctions are unavailable on this platform")
    command_processor = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    result = subprocess.run(  # noqa: S603 - fixed mklink command in a pytest temp directory
        [command_processor, "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or not link.is_junction():
        detail = (
            result.stderr.strip()
            or result.stdout.strip()
            or "mklink did not create a junction"
        )
        pytest.skip(f"Windows junction creation is unavailable: {detail}")


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    """A two-example dataset with its provenance sidecar beside it."""
    path = tmp_path / "source" / "dataset.jsonl"
    path.parent.mkdir()
    # With a system turn, because an exported dataset always carries one and
    # write_sidecar now reads the fingerprint out of it rather than stamping
    # whatever the code renders today.
    example = json.dumps(
        {
            "messages": [
                {"role": "system", "content": "A PROMPT"},
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "Final Answer: hello"},
            ]
        }
    )
    path.write_text(example + "\n" + example + "\n", encoding="utf-8")
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


def test_publish_refuses_destination_file_symlink_escape(
    dataset: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    outside = tmp_path / "outside-dataset.jsonl"
    outside.write_text("do not overwrite\n", encoding="utf-8")
    try:
        (dest / dataset.name).symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    with pytest.raises(PublishError, match="symlink or reparse point"):
        publish(dataset, dest, teacher="t")

    assert outside.read_text(encoding="utf-8") == "do not overwrite\n"


def test_publish_refuses_destination_hardlink_alias(
    dataset: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    outside = tmp_path / "outside-dataset.jsonl"
    outside.write_text("do not overwrite\n", encoding="utf-8")
    try:
        os.link(outside, dest / dataset.name)
    except OSError as exc:
        pytest.skip(f"hard links are unavailable: {exc}")

    with pytest.raises(PublishError, match="hard-linked"):
        publish(dataset, dest, teacher="t")

    assert outside.read_text(encoding="utf-8") == "do not overwrite\n"


def test_publish_refuses_destination_directory_junction_escape(
    dataset: Path, tmp_path: Path
) -> None:
    outside_bundle = tmp_path / "outside-bundle"
    outside_bundle.mkdir()
    dest = tmp_path / "drive-junction"
    _create_junction(dest, outside_bundle)

    with pytest.raises(PublishError, match="destination path contains a symlink or reparse point"):
        publish(dataset, dest, teacher="t")

    assert list(outside_bundle.iterdir()) == []


def test_verify_rejects_sha256sums_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside bundle\n", encoding="utf-8")
    (dest / "SHA256SUMS").write_text(
        f"{'0' * 64}  ../outside.txt\n", encoding="utf-8"
    )
    digested: list[Path] = []

    def record_digest(path: Path) -> str:
        digested.append(path)
        return ""

    monkeypatch.setattr("publish_dataset.digest", record_digest)

    assert verify(dest) == ["../outside.txt"]
    assert digested == []


def test_verify_refuses_oversized_sha256sums_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(publish_dataset, "MAX_SUMS_BYTES", 32)
    (dest / "SHA256SUMS").write_bytes(b"x" * 33)

    with pytest.raises(PublishError, match="byte verification limit"):
        verify(dest)


def test_verify_refuses_oversized_sha256sums_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(publish_dataset, "MAX_SUMS_LINE_BYTES", 8)
    (dest / "SHA256SUMS").write_bytes(b"x" * 9)

    with pytest.raises(PublishError, match="line over the 8-byte verification limit"):
        verify(dest)


def test_verify_refuses_too_many_sha256sums_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    monkeypatch.setattr(publish_dataset, "MAX_SUMS_ENTRIES", 1)
    (dest / "SHA256SUMS").write_text("\n\n", encoding="utf-8")

    with pytest.raises(PublishError, match="1-entry verification limit"):
        verify(dest)


@pytest.mark.parametrize("name", ["/outside.txt", "C:\\outside.txt", "nested/file.txt"])
def test_verify_rejects_absolute_or_nested_checksum_names(
    tmp_path: Path, name: str
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    (dest / "SHA256SUMS").write_text(f"{'0' * 64}  {name}\n", encoding="utf-8")

    assert verify(dest) == [name]


def test_verify_rejects_symlink_target_outside_bundle(tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside bundle\n", encoding="utf-8")
    try:
        (dest / "dataset.jsonl").symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    digest = sha256(outside.read_bytes()).hexdigest()
    (dest / "SHA256SUMS").write_text(f"{digest}  dataset.jsonl\n", encoding="utf-8")

    assert verify(dest) == ["dataset.jsonl"]


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


def test_verify_only_needs_nothing_but_a_destination(dataset: Path, tmp_path: Path) -> None:
    """Writing the docs exposed this: a re-check asked for a teacher it ignores.

    The verify path reads SHA256SUMS and nothing else, so requiring the
    dataset and --teacher made the documented command a lie.
    """
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")

    assert publish_dataset.main(["--verify-only", "--dest", str(dest)]) == 0


def test_verify_only_reports_a_tampered_bundle_as_failure(
    dataset: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    (dest / "dataset.jsonl").write_text("tampered\n", encoding="utf-8")

    assert publish_dataset.main(["--verify-only", "--dest", str(dest)]) == 1


def test_publishing_still_requires_a_dataset_and_a_teacher(tmp_path: Path) -> None:
    """Making them optional must not make them optional for a real publish.

    argparse exits 2 on a usage error rather than returning it, which is the
    convention every other CLI here follows.
    """
    with pytest.raises(SystemExit) as exit_info:
        publish_dataset.main(["--dest", str(tmp_path / "drive")])

    assert exit_info.value.code == 2
