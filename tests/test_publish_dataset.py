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
import shutil
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import publish_dataset
from publish_dataset import PublishError, publish, verify
from publish_dataset import main as publish_main

from dataset_provenance import prompt_fingerprint, write_sidecar
from publisher_root import PublisherRoot
from sandbox import Workspace


def _write_manifest(dest: Path, files: dict[str, str]) -> None:
    (dest / publish_dataset.MANIFEST_NAME).write_text(
        json.dumps(
            {
                "dataset": "dataset.jsonl",
                "examples": 1,
                "system_prompt_sha256": "a" * 64,
                "teacher_model": "test-teacher",
                "workspace_rule": None,
                "source_commit": None,
                "published_at": "2026-01-01T00:00:00+00:00",
                "files": files,
            }
        ),
        encoding="utf-8",
    )


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
            result.stderr.strip() or result.stdout.strip() or "mklink did not create a junction"
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


@pytest.mark.parametrize("mutation", ["prompt-fingerprint", "example-count", "dataset-identity"])
@pytest.mark.parametrize("destination_exists", [False, True])
def test_publish_rejects_sidecar_that_does_not_match_live_dataset(
    dataset: Path,
    tmp_path: Path,
    mutation: str,
    destination_exists: bool,
) -> None:
    sidecar = dataset.with_name(dataset.name + ".provenance.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    if mutation == "prompt-fingerprint":
        payload["system_prompt_sha256"] = prompt_fingerprint()
        payload["matches_live_prompt"] = True
    elif mutation == "example-count":
        payload["examples"] += 1
    else:
        payload["dataset"] = "other.jsonl"
    sidecar.write_text(json.dumps(payload), encoding="utf-8")
    sidecar_before = sidecar.read_bytes()

    dest = tmp_path / "existing-drive"
    if destination_exists:
        dest.mkdir()
        (dest / "keep.txt").write_text("keep this bundle\n", encoding="utf-8")
    before = {path.name: path.read_bytes() for path in dest.iterdir()} if dest.exists() else {}

    with pytest.raises(PublishError, match="provenance sidecar"):
        publish(dataset, dest, teacher="qwen2.5-coder:7b")

    assert dest.exists() is destination_exists
    after = {path.name: path.read_bytes() for path in dest.iterdir()} if dest.exists() else {}
    assert after == before
    assert sidecar.read_bytes() == sidecar_before


def test_publish_rejects_symlink_sidecar_without_mutating_destination(
    dataset: Path, tmp_path: Path
) -> None:
    sidecar = dataset.with_name(dataset.name + ".provenance.json")
    external = tmp_path / "external-provenance.json"
    external.write_bytes(sidecar.read_bytes())
    sidecar.unlink()
    try:
        sidecar.symlink_to(external)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    sidecar_before = sidecar.read_bytes()
    dest = tmp_path / "existing-drive"
    dest.mkdir()
    keep = dest / "keep.txt"
    keep.write_text("keep this bundle\n", encoding="utf-8")

    with pytest.raises(PublishError, match="missing or invalid"):
        publish(dataset, dest, teacher="qwen2.5-coder:7b")

    assert list(dest.iterdir()) == [keep]
    assert keep.read_text(encoding="utf-8") == "keep this bundle\n"
    assert sidecar.is_symlink()
    assert sidecar.read_bytes() == sidecar_before
    assert external.read_bytes() == sidecar_before


@pytest.mark.parametrize(
    "invalid_kind",
    ["malformed", "secret", "top-level-extra", "message-extra"],
)
@pytest.mark.parametrize("destination_exists", [False, True])
def test_publish_cli_refuses_invalid_dataset_without_mutating_destination(
    dataset: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    invalid_kind: str,
    destination_exists: bool,
) -> None:
    if invalid_kind == "malformed":
        dataset.write_text("not JSON\n", encoding="utf-8")
    else:
        contents = dataset.read_text(encoding="utf-8")
        if invalid_kind == "secret":
            contents = contents.replace(
                "Final Answer: hello",
                "Final Answer: API_KEY=sk-abcdefghijklmnop12345",
            )
        else:
            records = [json.loads(line) for line in contents.splitlines()]
            for record in records:
                if invalid_kind == "top-level-extra":
                    record["metadata"] = "API_KEY=sk-abcdefghijklmnop12345"
                else:
                    record["messages"][1]["metadata"] = "API_KEY=sk-abcdefghijklmnop12345"
            contents = "\n".join(json.dumps(record) for record in records) + "\n"
        dataset.write_text(contents, encoding="utf-8")

    dest = tmp_path / "drive"
    if destination_exists:
        dest.mkdir()
        (dest / "sentinel.txt").write_bytes(b"preserve sentinel\n")
        (dest / dataset.name).write_bytes(b"preserve previous dataset\n")
        before = {
            path.relative_to(dest).as_posix(): path.read_bytes()
            for path in dest.rglob("*")
            if path.is_file()
        }

    result = publish_main(
        [str(dataset), "--local-only-path", str(dest), "--teacher", "synthetic-teacher"]
    )

    assert result == 1
    assert "credential/schema validation" in capsys.readouterr().err
    if destination_exists:
        after = {
            path.relative_to(dest).as_posix(): path.read_bytes()
            for path in dest.rglob("*")
            if path.is_file()
        }
        assert after == before
    else:
        assert not dest.exists()


def test_publish_cli_still_publishes_valid_dataset(
    dataset: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest = tmp_path / "drive"

    result = publish_main(
        [str(dataset), "--local-only-path", str(dest), "--teacher", "synthetic-teacher"]
    )

    assert result == 0
    assert "published" in capsys.readouterr().out
    assert verify(dest) == []


def test_publish_refuses_duplicate_source_basenames_without_mutating_destination(
    dataset: Path, tmp_path: Path
) -> None:
    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    duplicate = extra_dir / dataset.name
    duplicate.write_text("extra source\n", encoding="utf-8")
    dest = tmp_path / "drive"
    dest.mkdir()
    (dest / "sentinel.txt").write_bytes(b"preserve sentinel\n")
    (dest / dataset.name).write_bytes(b"preserve old dataset\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()}

    with pytest.raises(PublishError, match="duplicate basenames"):
        publish(dataset, dest, teacher="synthetic-teacher", extras=(duplicate,))

    assert {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()} == before


@pytest.mark.parametrize(
    "unsafe_name",
    [
        "dataset.jsonl.",
        "dataset.jsonl ",
        "CON",
        "con.txt",
        "NUL.jsonl",
        "COM1.data",
        "lpt9.txt",
        "COM¹.log",
        "CON .jsonl",
    ],
)
def test_publish_refuses_windows_alias_names_before_destination_mutation(
    dataset: Path, tmp_path: Path, unsafe_name: str
) -> None:
    class NamedSource:
        def __init__(self, name: str) -> None:
            self.name = name

        def is_file(self) -> bool:
            return True

        def __str__(self) -> str:
            return self.name

    dest = tmp_path / "drive"
    dest.mkdir()
    sentinel = dest / "sentinel.txt"
    sentinel.write_bytes(b"preserve sentinel\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()}
    unsafe_source = cast(Path, NamedSource(unsafe_name))

    with pytest.raises(PublishError, match="basename is not safe"):
        publish(dataset, dest, teacher="synthetic-teacher", extras=(unsafe_source,))

    assert {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()} == before


@pytest.mark.parametrize(
    "unsafe_name",
    ["bad\nname.txt", "bad\rname.txt", "bad\x01name.txt", "bad\u0085name.txt"],
)
def test_publish_refuses_control_characters_in_names_before_mutation(
    dataset: Path, tmp_path: Path, unsafe_name: str
) -> None:
    class NamedSource:
        def __init__(self, name: str) -> None:
            self.name = name

        def __str__(self) -> str:
            return self.name

    dest = tmp_path / "drive"
    dest.mkdir()
    sentinel = dest / "sentinel.txt"
    sentinel.write_bytes(b"preserve sentinel\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir()}

    with pytest.raises(PublishError, match="basename is not safe"):
        publish(
            dataset,
            dest,
            teacher="synthetic-teacher",
            extras=(cast(Path, NamedSource(unsafe_name)),),
        )

    assert {path.name: path.read_bytes() for path in dest.iterdir()} == before


@pytest.mark.skipif(os.name != "nt", reason="Windows junction listing privacy")
def test_workspace_listing_hides_junction_canary(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "normal.txt").write_text("normal", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "UNIQUE-JUNCTION-LISTING-CANARY.txt").write_text("outside secret", encoding="utf-8")
    _create_junction(root / "redirect", outside)
    workspace = Workspace.at(root)
    try:
        entries = workspace.list_dir(".")
    finally:
        workspace.close()

    assert any(entry.startswith("normal.txt") for entry in entries)
    assert not any("redirect" in entry for entry in entries)
    assert not any("UNIQUE-JUNCTION-LISTING-CANARY" in entry for entry in entries)


@pytest.mark.parametrize(
    "reserved_name", [publish_dataset.MANIFEST_NAME, publish_dataset.SUMS_NAME]
)
@pytest.mark.parametrize("source_kind", ["dataset", "extra"])
def test_publish_refuses_source_basename_reserved_for_generated_files(
    dataset: Path, tmp_path: Path, reserved_name: str, source_kind: str
) -> None:
    if source_kind == "dataset":
        source = tmp_path / "reserved-source" / reserved_name
        source.parent.mkdir()
        source.write_text(dataset.read_text(encoding="utf-8"), encoding="utf-8")
        write_sidecar(source)
        publish_dataset_path = source
        extras: tuple[Path, ...] = ()
    else:
        extra = tmp_path / "reserved-extra" / reserved_name
        extra.parent.mkdir()
        extra.write_text("extra source\n", encoding="utf-8")
        publish_dataset_path = dataset
        extras = (extra,)
    dest = tmp_path / "drive"
    dest.mkdir()
    (dest / "sentinel.txt").write_bytes(b"preserve sentinel\n")
    (dest / reserved_name).write_bytes(b"preserve generated-name collision\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()}

    with pytest.raises(PublishError, match="collides with a generated bundle file"):
        publish(
            publish_dataset_path,
            dest,
            teacher="synthetic-teacher",
            extras=extras,
        )

    assert {path.name: path.read_bytes() for path in dest.iterdir() if path.is_file()} == before


@pytest.mark.parametrize("overflow_kind", ["extra", "aggregate"])
def test_publish_bundle_cap_refuses_before_destination_mutation(
    dataset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overflow_kind: str,
) -> None:
    sidecar = dataset.with_name(dataset.name + ".provenance.json")
    extras: tuple[Path, ...]
    sources = [dataset, sidecar]
    if overflow_kind == "extra":
        extra = dataset.parent / "large-extra.log"
        extra.write_bytes(b"x" * 4096)
        extras = (extra,)
        monkeypatch.setattr(
            publish_dataset,
            "MAX_BUNDLE_BYTES",
            sum(path.stat().st_size for path in sources) + 64,
        )
        assert extra.stat().st_size > publish_dataset.MAX_BUNDLE_BYTES - sum(
            path.stat().st_size for path in sources
        )
    else:
        first_extra = dataset.parent / "first-extra.log"
        second_extra = dataset.parent / "second-extra.log"
        first_extra.write_bytes(b"a" * 64)
        second_extra.write_bytes(b"b" * 64)
        extras = (first_extra, second_extra)
        sources.extend(extras)
        source_total = sum(path.stat().st_size for path in sources)
        monkeypatch.setattr(publish_dataset, "MAX_BUNDLE_BYTES", source_total - 1)
        assert all(path.stat().st_size < publish_dataset.MAX_BUNDLE_BYTES for path in sources)

    dest = tmp_path / "existing-drive"
    dest.mkdir()
    (dest / "sentinel.txt").write_bytes(b"preserve existing bundle\n")
    (dest / dataset.name).write_bytes(b"old dataset copy\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir()}
    copy_calls: list[Path] = []
    real_copy2 = shutil.copy2

    def observe_copy(source: Path, target: Path) -> Path:
        copy_calls.append(source)
        real_copy2(source, target)
        return target

    monkeypatch.setattr(shutil, "copy2", observe_copy)
    with pytest.raises(PublishError, match="aggregate bundle byte limit"):
        publish(dataset, dest, teacher="synthetic-teacher", extras=extras)

    assert copy_calls == []
    assert {path.name: path.read_bytes() for path in dest.iterdir()} == before


def test_publish_counts_generated_metadata_in_bundle_byte_cap(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sidecar = dataset.with_name(dataset.name + ".provenance.json")
    source_bytes = dataset.stat().st_size + sidecar.stat().st_size
    monkeypatch.setattr(publish_dataset, "MAX_BUNDLE_BYTES", source_bytes + 1)
    dest = tmp_path / "existing-drive"
    dest.mkdir()
    (dest / "sentinel.txt").write_bytes(b"preserve existing bundle\n")
    before = {path.name: path.read_bytes() for path in dest.iterdir()}

    with pytest.raises(PublishError, match="aggregate bundle byte limit"):
        publish(dataset, dest, teacher="synthetic-teacher")

    assert {path.name: path.read_bytes() for path in dest.iterdir()} == before


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


@pytest.mark.parametrize(
    ("metadata", "message"),
    [
        (
            ("teacher", "t" * (publish_dataset.MAX_TEACHER_MODEL_BYTES + 1)),
            "teacher metadata",
        ),
        (
            ("workspace_rule", "é" * (publish_dataset.MAX_WORKSPACE_RULE_BYTES // 2 + 1)),
            "workspace rule metadata",
        ),
    ],
)
@pytest.mark.parametrize("api", ["publish", "publish_to_root"])
def test_public_publish_apis_refuse_oversized_metadata_before_destination_creation(
    dataset: Path,
    tmp_path: Path,
    metadata: tuple[str, str],
    message: str,
    api: str,
) -> None:
    field, value = metadata
    dest = tmp_path / "oversized-metadata-bundle"
    teacher = value if field == "teacher" else "bounded-teacher"
    workspace_rule = value if field == "workspace_rule" else None
    call: Callable[[], object]
    if api == "publish":
        call = lambda: publish(  # noqa: E731 - keep parametrized API invocation explicit
            dataset, dest, teacher=teacher, workspace_rule=workspace_rule
        )
    else:
        fake_root = cast(
            PublisherRoot,
            type("UntouchedRoot", (), {"path": dest.parent})(),
        )
        call = lambda: publish_dataset.publish_to_root(  # noqa: E731 - see above
            dataset,
            fake_root,
            dest.name,
            teacher=teacher,
            workspace_rule=workspace_rule,
        )

    with pytest.raises(PublishError, match=message):
        call()

    assert not dest.exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows AppContainer cannot provide private staging")
def test_metadata_at_byte_limits_publishes_and_verifies(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "maximum-metadata-bundle"
    teacher = "t" * publish_dataset.MAX_TEACHER_MODEL_BYTES
    workspace_rule = "é" * (publish_dataset.MAX_WORKSPACE_RULE_BYTES // 2)

    manifest = publish(dataset, dest, teacher=teacher, workspace_rule=workspace_rule)

    assert manifest["teacher_model"] == teacher
    assert manifest["workspace_rule"] == workspace_rule
    assert verify(dest) == []


@pytest.mark.skipif(os.name == "nt", reason="Windows AppContainer cannot provide private staging")
def test_oversized_encoded_manifest_refuses_before_staging(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "oversized-manifest-bundle"
    monkeypatch.setattr(publish_dataset, "MAX_MANIFEST_BYTES", 1)

    with pytest.raises(PublishError, match=r"MANIFEST\.json exceeds"):
        publish(dataset, dest, teacher="synthetic-teacher")

    assert not dest.exists()
    assert not list(tmp_path.glob(".omniagent-publish-*"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("teacher_model", "t" * (publish_dataset.MAX_TEACHER_MODEL_BYTES + 1)),
        ("workspace_rule", "w" * (publish_dataset.MAX_WORKSPACE_RULE_BYTES + 1)),
    ],
)
def test_manifest_parser_rejects_metadata_over_byte_limits(field: str, value: str) -> None:
    manifest = {
        "dataset": "dataset.jsonl",
        "examples": 1,
        "system_prompt_sha256": "a" * 64,
        "teacher_model": "valid-teacher",
        "workspace_rule": None,
        "source_commit": None,
        "published_at": "2026-01-01T00:00:00+00:00",
        "files": {},
    }
    manifest[field] = value

    with pytest.raises(PublishError, match=r"MANIFEST\.json contains invalid metadata"):
        publish_dataset._read_manifest(json.dumps(manifest).encode("utf-8"))


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


@pytest.mark.parametrize(
    "name",
    [
        publish_dataset.SUMS_NAME,
        publish_dataset.MANIFEST_NAME,
        "dataset.jsonl",
        "dataset.jsonl.provenance.json",
    ],
)
def test_verify_leaf_swap_after_open_uses_only_the_pinned_bytes(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    outside = tmp_path / "outside-unique-canary"
    outside.write_text("UNIQUE-OUTSIDE-VERIFY-CANARY\n", encoding="utf-8")
    target = dest / name
    real_checkpoint = publish_dataset._verify_checkpoint
    swapped = False

    def swap_after_open(phase: str) -> None:
        nonlocal swapped
        if phase == f"opened:{name}" and not swapped:
            swapped = True
            moved = dest / f"{name}.pinned-copy"
            try:
                target.rename(moved)
                try:
                    target.symlink_to(outside)
                except OSError:
                    moved.rename(target)
                    raise
            except OSError:
                # Windows verification handles deny write/delete sharing.
                pass
        real_checkpoint(phase)

    monkeypatch.setattr(publish_dataset, "_verify_checkpoint", swap_after_open)
    assert verify(dest) == []
    assert outside.read_text(encoding="utf-8") == "UNIQUE-OUTSIDE-VERIFY-CANARY\n"


def test_verify_names_a_file_that_changed_after_the_copy(dataset: Path, tmp_path: Path) -> None:
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


def test_publishing_to_an_existing_bundle_fails_without_changing_it(
    dataset: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    before = {path.name: path.read_bytes() for path in dest.iterdir()}

    with pytest.raises(PublishError, match="destination is not empty"):
        publish(dataset, dest, teacher="t")

    assert {path.name: path.read_bytes() for path in dest.iterdir()} == before
    assert verify(dest) == []


def test_publish_refuses_destination_file_symlink_escape(dataset: Path, tmp_path: Path) -> None:
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


def test_publish_refuses_destination_hardlink_alias(dataset: Path, tmp_path: Path) -> None:
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
    (dest / "SHA256SUMS").write_text(f"{'0' * 64}  ../outside.txt\n", encoding="utf-8")
    _write_manifest(dest, {})
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


def test_verify_rejects_duplicate_filenames_without_hashing_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    payload = dest / "dataset.jsonl"
    payload.write_bytes(b"dataset payload")
    value = publish_dataset.digest(payload)
    (dest / "SHA256SUMS").write_text(
        f"{value}  {payload.name}\n{value}  {payload.name}\n", encoding="utf-8"
    )
    _write_manifest(dest, {payload.name: value})
    digested: list[Path] = []

    real_checkpoint = publish_dataset._verify_checkpoint

    def record_checkpoint(phase: str) -> None:
        if phase.startswith("opened:") and phase not in {
            f"opened:{publish_dataset.SUMS_NAME}",
            f"opened:{publish_dataset.MANIFEST_NAME}",
        }:
            digested.append(Path(phase.removeprefix("opened:")))
        real_checkpoint(phase)

    monkeypatch.setattr(publish_dataset, "_verify_checkpoint", record_checkpoint)

    assert verify(dest) == [payload.name]
    assert len(digested) == 1
    assert digested[0].name == payload.name


def test_verify_stops_at_aggregate_hash_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    first = dest / "a.jsonl"
    second = dest / "b.jsonl"
    first.write_bytes(b"1234")
    second.write_bytes(b"5678")
    first_digest = publish_dataset.digest(first)
    second_digest = publish_dataset.digest(second)
    (dest / "SHA256SUMS").write_text(
        f"{first_digest}  {first.name}\n{second_digest}  {second.name}\n",
        encoding="utf-8",
    )
    _write_manifest(dest, {first.name: first_digest, second.name: second_digest})
    monkeypatch.setattr(
        publish_dataset,
        "MAX_BUNDLE_BYTES",
        (dest / "SHA256SUMS").stat().st_size
        + (dest / "MANIFEST.json").stat().st_size
        + first.stat().st_size
        + second.stat().st_size
        - 1,
    )
    digested: list[Path] = []

    real_checkpoint = publish_dataset._verify_checkpoint

    def record_checkpoint(phase: str) -> None:
        if phase.startswith("opened:") and phase not in {
            f"opened:{publish_dataset.SUMS_NAME}",
            f"opened:{publish_dataset.MANIFEST_NAME}",
        }:
            digested.append(Path(phase.removeprefix("opened:")))
        real_checkpoint(phase)

    monkeypatch.setattr(publish_dataset, "_verify_checkpoint", record_checkpoint)

    with pytest.raises(PublishError, match="aggregate bundle byte limit"):
        verify(dest)

    assert [path.name for path in digested] == [first.name]


@pytest.mark.parametrize("name", ["/outside.txt", "C:\\outside.txt", "nested/file.txt"])
def test_verify_rejects_absolute_or_nested_checksum_names(tmp_path: Path, name: str) -> None:
    dest = tmp_path / "drive"
    dest.mkdir()
    (dest / "SHA256SUMS").write_text(f"{'0' * 64}  {name}\n", encoding="utf-8")
    _write_manifest(dest, {})

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
    _write_manifest(dest, {"dataset.jsonl": digest})

    assert verify(dest) == ["dataset.jsonl"]


@pytest.mark.parametrize(
    "failure_phase",
    [
        "stage-created",
        "first-payload",
        "all-payloads",
        "checksums-written",
        "manifest-written",
        "verified",
        "promotion",
    ],
)
def test_publish_interruption_never_exposes_an_incomplete_destination(
    dataset: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_phase: str,
) -> None:
    dest = tmp_path / "drive"

    def interrupt(phase: str) -> None:
        if phase == failure_phase:
            raise OSError(f"injected {phase} failure")

    monkeypatch.setattr(publish_dataset, "_publish_checkpoint", interrupt)

    with pytest.raises(PublishError, match="atomic publication failed"):
        publish(dataset, dest, teacher="synthetic-teacher")

    assert not dest.exists()
    assert list(tmp_path.glob(f"{publish_dataset._STAGING_PREFIX}*")) == []
    with pytest.raises(PublishError):
        verify(dest)


def test_verifier_rejects_a_complete_but_unpublished_staging_directory(
    dataset: Path, tmp_path: Path
) -> None:
    published = tmp_path / "published"
    publish(dataset, published, teacher="synthetic-teacher")
    staging = tmp_path / f"{publish_dataset._STAGING_PREFIX}leftover"
    shutil.copytree(published, staging)

    with pytest.raises(PublishError, match="unpublished staging"):
        verify(staging)


def test_verifier_rejects_a_stale_manifest(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="synthetic-teacher")
    stale = json.loads((dest / publish_dataset.MANIFEST_NAME).read_text("utf-8"))
    stale["files"][dataset.name] = "0" * 64
    (dest / publish_dataset.MANIFEST_NAME).write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(PublishError, match="does not match SHA256SUMS"):
        verify(dest)


def test_verifier_rejects_duplicate_manifest_keys(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="synthetic-teacher")
    path = dest / publish_dataset.MANIFEST_NAME
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"dataset": ',
        '"dataset": "duplicate.jsonl",\n  "dataset": ',
        1,
    )
    path.write_text(text, encoding="utf-8")

    with pytest.raises(PublishError, match="duplicate JSON keys"):
        verify(dest)


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ("missing", "teacher_model"),
        ("extra", "unexpected"),
        ("wrong-type", "workspace_rule"),
        ("bad-prompt", "system_prompt_sha256"),
        ("bad-commit", "source_commit"),
        ("bad-time", "published_at"),
        ("empty-teacher", "teacher_model"),
        ("overlong-teacher", "teacher_model"),
        ("overlong-workspace", "workspace_rule"),
    ],
)
def test_verifier_rejects_invalid_manifest_schema_or_metadata(
    dataset: Path,
    tmp_path: Path,
    mutation: str,
    field: str,
) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="synthetic-teacher")
    path = dest / publish_dataset.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if mutation == "missing":
        manifest.pop(field)
    elif mutation == "extra":
        manifest[field] = "unexpected"
    elif mutation == "wrong-type":
        manifest[field] = 17
    elif mutation == "bad-prompt":
        manifest[field] = "not-a-sha256"
    elif mutation == "bad-commit":
        manifest[field] = "not-a-git-commit"
    elif mutation == "bad-time":
        manifest[field] = "yesterday"
    elif mutation == "overlong-teacher":
        manifest[field] = "t" * (publish_dataset.MAX_TEACHER_MODEL_BYTES + 1)
    elif mutation == "overlong-workspace":
        manifest[field] = "w" * (publish_dataset.MAX_WORKSPACE_RULE_BYTES + 1)
    else:
        manifest[field] = "  "
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublishError, match=r"MANIFEST\.json"):
        verify(dest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("dataset", "different.jsonl"),
        ("examples", 99),
        ("system_prompt_sha256", "0" * 64),
    ],
)
def test_verifier_binds_dataset_metadata_to_validated_data_and_sidecar(
    dataset: Path,
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="synthetic-teacher")
    path = dest / publish_dataset.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest[field] = value
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublishError, match=r"provenance does not match|dataset is not bound"):
        verify(dest)


def test_verifier_process_rejects_an_incomplete_bundle(
    tmp_path: Path,
) -> None:
    dest = tmp_path / "interrupted-drive"
    dest.mkdir()
    payload = dest / "dataset.jsonl"
    payload.write_bytes(b"partial bundle")
    (dest / publish_dataset.SUMS_NAME).write_text(
        f"{sha256(payload.read_bytes()).hexdigest()}  {payload.name}\n", encoding="utf-8"
    )

    result = subprocess.run(  # noqa: S603 - fixed local verifier and pytest temporary destination
        [
            sys.executable,
            str(Path(publish_dataset.__file__)),
            "--verify-only",
            "--local-only-path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "MANIFEST.json" in result.stderr


def test_atomic_publish_preserves_existing_valid_destination(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "existing-drive"
    publish(dataset, dest, teacher="original-teacher")
    before = {path.name: path.read_bytes() for path in dest.iterdir()}

    with pytest.raises(PublishError, match="destination is not empty"):
        publish(dataset, dest, teacher="replacement-teacher")

    assert {path.name: path.read_bytes() for path in dest.iterdir()} == before
    result = subprocess.run(  # noqa: S603 - fixed local verifier and pytest temporary destination
        [
            sys.executable,
            str(Path(publish_dataset.__file__)),
            "--verify-only",
            "--local-only-path",
            str(dest),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "verified"


def test_empty_destination_replacement_is_atomic_or_fails_closed(
    dataset: Path, tmp_path: Path
) -> None:
    dest = tmp_path / "empty-drive"
    dest.mkdir()

    if os.name == "nt":
        with pytest.raises(PublishError, match="atomic publication failed"):
            publish(dataset, dest, teacher="synthetic-teacher")
        assert list(dest.iterdir()) == []
    else:
        publish(dataset, dest, teacher="synthetic-teacher")
        assert verify(dest) == []

    assert list(tmp_path.glob(f"{publish_dataset._STAGING_PREFIX}*")) == []


def test_a_copy_that_arrives_different_fails_the_publish(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard no other test here reaches: corruption during the copy.

    verify() covers a file that changed afterwards. This covers the write
    itself coming back wrong, which on a removable volume is the case worth
    failing loudly on rather than discovering during training.
    """
    real_write = publish_dataset.SecureRoot.write

    def truncated_write(root: object, handle: int, content: bytes) -> None:
        real_write(root, handle, b"half a fi")  # type: ignore[arg-type]

    monkeypatch.setattr(publish_dataset.SecureRoot, "write", truncated_write)

    with pytest.raises(PublishError, match="does not match the source"):
        publish(dataset, tmp_path / "drive", teacher="t")


def test_source_leaf_swap_after_open_never_publishes_the_outside_canary(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "outside-canary.jsonl"
    outside.write_text("UNIQUE-OUTSIDE-CANARY\n", encoding="utf-8")
    original = dataset.read_bytes()
    real_read = publish_dataset._OpenedSource.read_bounded
    swapped = False

    def swap_then_read(source: object, limit: int) -> bytes:
        nonlocal swapped
        if not swapped and source.path == dataset:  # type: ignore[attr-defined]
            swapped = True
            moved = dataset.with_suffix(".held")
            try:
                dataset.rename(moved)
                try:
                    dataset.symlink_to(outside)
                except OSError:
                    moved.rename(dataset)
                    raise
            except OSError:
                # Windows share flags deny rename while the source handle is
                # open; that is the expected fail-closed race outcome.
                pass
        return real_read(source, limit)  # type: ignore[arg-type]

    monkeypatch.setattr(publish_dataset._OpenedSource, "read_bounded", swap_then_read)
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    assert (dest / dataset.name).read_bytes() == original
    assert outside.read_text(encoding="utf-8") == "UNIQUE-OUTSIDE-CANARY\n"


def test_opened_source_closes_file_handle_when_metadata_read_fails(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[int] = []
    real_close = publish_dataset.SecureRoot.close_handle

    def fail_info(_root: object, _handle: int) -> tuple[int, int, bool]:
        raise OSError("injected info failure")

    def record_close(root: object, handle: int) -> None:
        closed.append(handle)
        real_close(root, handle)  # type: ignore[arg-type]

    monkeypatch.setattr(publish_dataset.SecureRoot, "info", fail_info)
    monkeypatch.setattr(publish_dataset.SecureRoot, "close_handle", record_close)
    with pytest.raises(OSError, match="injected info failure"):
        publish_dataset._OpenedSource(dataset)
    assert len(closed) == 1


def test_dataset_mutation_after_snapshot_cannot_change_published_bytes(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = dataset.read_bytes()
    real_read = publish_dataset._OpenedSource.read_bounded
    mutated = False

    def mutate_after_snapshot(source: object, limit: int) -> bytes:
        nonlocal mutated
        content = real_read(source, limit)  # type: ignore[arg-type]
        if not mutated and source.path == dataset:  # type: ignore[attr-defined]
            mutated = True
            with suppress(PermissionError):
                dataset.write_bytes(b"UNIQUE-MUTATION-CANARY\n")
                # The Windows source handle denies write sharing.
        return content

    monkeypatch.setattr(publish_dataset._OpenedSource, "read_bounded", mutate_after_snapshot)
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    assert (dest / dataset.name).read_bytes() == original


def test_extra_is_snapshotted_before_manifest_and_stage_creation(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    extra = tmp_path / "raw.log"
    original = b"raw source bytes before staging\n"
    extra.write_bytes(original)
    real_checkpoint = publish_dataset._publish_checkpoint

    def mutate_after_snapshot(phase: str) -> None:
        if phase == "stage-created":
            with suppress(PermissionError):
                extra.write_bytes(b"UNIQUE-LATE-MUTATION-CANARY\n")
                # Windows source handle is opened without write sharing.
        real_checkpoint(phase)

    monkeypatch.setattr(publish_dataset, "_publish_checkpoint", mutate_after_snapshot)
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t", extras=(extra,))
    assert (dest / extra.name).read_bytes() == original


def test_destination_target_race_uses_atomic_no_replace(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest = tmp_path / "drive"
    sentinel = dest / "sentinel.txt"

    def occupy_target(phase: str) -> None:
        if phase == "promotion":
            dest.mkdir()
            sentinel.write_text("UNIQUE-TARGET-CANARY\n", encoding="utf-8")

    monkeypatch.setattr(publish_dataset, "_publish_checkpoint", occupy_target)
    with pytest.raises(PublishError, match="atomic publication failed"):
        publish(dataset, dest, teacher="t")
    assert sentinel.read_text(encoding="utf-8") == "UNIQUE-TARGET-CANARY\n"
    assert not (dest / dataset.name).exists()
    assert list(tmp_path.glob(f"{publish_dataset._STAGING_PREFIX}*")) == []


def test_destination_parent_swap_never_writes_through_the_replacement(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "publish-parent"
    parent.mkdir()
    destination = parent / "drive"
    outside = tmp_path / "outside-parent"
    outside.mkdir()
    original_checkpoint = publish_dataset._publish_checkpoint
    swapped = False

    def swap_parent(phase: str) -> None:
        nonlocal swapped
        if phase == "stage-created" and not swapped:
            swapped = True
            moved = tmp_path / "pinned-parent"
            try:
                parent.rename(moved)
                try:
                    parent.symlink_to(outside, target_is_directory=True)
                except OSError:
                    moved.rename(parent)
                    raise
            except OSError:
                # Windows share flags deny parent rename while its handle is
                # retained; the pinned parent remains the only publish target.
                pass
        original_checkpoint(phase)

    monkeypatch.setattr(publish_dataset, "_publish_checkpoint", swap_parent)
    publish(dataset, destination, teacher="t")
    assert not (outside / "drive").exists()
    if parent.is_symlink():
        parent.unlink()
    moved = tmp_path / "pinned-parent"
    if moved.exists():
        assert (moved / "drive" / dataset.name).is_file()
    else:
        assert (parent / "drive" / dataset.name).is_file()


def test_verify_only_needs_nothing_but_a_destination(dataset: Path, tmp_path: Path) -> None:
    """Writing the docs exposed this: a re-check asked for a teacher it ignores.

    The verify path reads SHA256SUMS and nothing else, so requiring the
    dataset and --teacher made the documented command a lie.
    """
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")

    assert publish_dataset.main(["--verify-only", "--local-only-path", str(dest)]) == 0


def test_verify_only_reports_a_tampered_bundle_as_failure(dataset: Path, tmp_path: Path) -> None:
    dest = tmp_path / "drive"
    publish(dataset, dest, teacher="t")
    (dest / "dataset.jsonl").write_text("tampered\n", encoding="utf-8")

    assert publish_dataset.main(["--verify-only", "--local-only-path", str(dest)]) == 1


def test_publishing_still_requires_a_dataset_and_a_teacher(tmp_path: Path) -> None:
    """Making them optional must not make them optional for a real publish.

    argparse exits 2 on a usage error rather than returning it, which is the
    convention every other CLI here follows.
    """
    with pytest.raises(SystemExit) as exit_info:
        publish_dataset.main(["--local-only-path", str(tmp_path / "drive")])

    assert exit_info.value.code == 2
