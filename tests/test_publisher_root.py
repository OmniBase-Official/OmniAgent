"""Tests for the current-user publisher profile capability."""

from __future__ import annotations

import ctypes
import os
import stat
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import publish_dataset

import publisher_root
from dataset_provenance import write_sidecar
from publisher_root import PublisherRoot, PublisherRootError
from securefs import SecureRoot


@pytest.fixture
def isolated_profile(
    monkeypatch: pytest.MonkeyPatch, owner_private_test_root: Path
) -> Path:
    base = owner_private_test_root
    app_directory = f"OmniAgent-test-{uuid.uuid4().hex}"
    monkeypatch.setattr(publisher_root, "_known_local_data_root", lambda: base)
    monkeypatch.setattr(publisher_root, "_APP_DIRECTORY", app_directory)
    if os.name == "nt":
        monkeypatch.setattr(publisher_root, "_windows_standard_token", lambda: True)
    return base


def _dataset(path: Path) -> Path:
    dataset = path / "dataset.jsonl"
    dataset.write_text(
        '{"messages":[{"role":"system","content":"test"},'
        '{"role":"user","content":"input"},'
        '{"role":"assistant","content":"output"}]}\n',
        encoding="utf-8",
    )
    write_sidecar(dataset)
    return dataset


def _synthetic_publisher_path() -> Path:
    if os.name == "nt":
        return Path("C:/system/home/alice/data")
    return Path("/system/home/alice/data")


def _mock_posix_ancestors(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    *,
    current_uid: int,
    overrides: dict[Path, tuple[int, int]],
) -> None:
    directories = (target, *target.parents)
    metadata = {directory: overrides.get(directory, (0, 0o755)) for directory in directories}

    def fake_stat(directory: Path, *, follow_symlinks: bool = True) -> SimpleNamespace:
        _ = follow_symlinks
        uid, mode = metadata[directory]
        return SimpleNamespace(st_uid=uid, st_mode=stat.S_IFDIR | mode)

    monkeypatch.setattr(Path, "stat", fake_stat)
    monkeypatch.setattr(Path, "is_symlink", lambda _directory: False)
    monkeypatch.setattr(os, "geteuid", lambda: current_uid, raising=False)
    monkeypatch.setattr(
        publisher_root,
        "_acl_has_foreign_write_execute",
        lambda _directory, _attribute: False,
    )


def test_non_windows_token_check_remains_a_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")

    assert publisher_root._windows_standard_token()


def test_windows_dll_loader_preserves_last_error_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []
    library = cast(ctypes.CDLL, object())

    def fake_loader(name: str, *, use_last_error: bool) -> ctypes.CDLL:
        calls.append((name, use_last_error))
        return library

    monkeypatch.setattr(ctypes, "WinDLL", fake_loader, raising=False)

    assert publisher_root._load_windows_dll("advapi32") is library
    assert calls == [("advapi32", True)]


def test_posix_ancestor_validation_accepts_root_and_user_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _synthetic_publisher_path()
    current_uid = 1000
    user_home = target.parents[0]
    _mock_posix_ancestors(
        monkeypatch,
        target,
        current_uid=current_uid,
        overrides={user_home: (current_uid, 0o700), target: (current_uid, 0o700)},
    )

    publisher_root._validate_posix_ancestors(target)


def test_posix_ancestor_validation_rejects_foreign_owner_write_and_traverse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _synthetic_publisher_path()
    current_uid = 1000
    foreign_home = target.parents[0]
    _mock_posix_ancestors(
        monkeypatch,
        target,
        current_uid=current_uid,
        overrides={foreign_home: (2000, 0o700), target: (current_uid, 0o700)},
    )

    with pytest.raises(PublisherRootError, match="foreign owner can write and traverse"):
        publisher_root._validate_posix_ancestors(target)


def test_posix_ancestor_validation_rejects_foreign_group_write_and_traverse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _synthetic_publisher_path()
    current_uid = 1000
    shared_home = target.parents[1]
    _mock_posix_ancestors(
        monkeypatch,
        target,
        current_uid=current_uid,
        overrides={shared_home: (0, 0o733), target: (current_uid, 0o700)},
    )

    with pytest.raises(PublisherRootError, match="foreign group or users"):
        publisher_root._validate_posix_ancestors(target)


def test_profile_provision_and_open_are_bound_to_one_user_root(isolated_profile: Path) -> None:
    with PublisherRoot.provision_local_user() as provisioned:
        expected = isolated_profile / publisher_root._APP_DIRECTORY / "publish"
        assert provisioned.path == expected
        assert expected.is_dir()
    with PublisherRoot.open_local_user() as opened:
        assert opened.path == expected


def test_destination_name_rejects_paths_and_reserved_names(isolated_profile: Path) -> None:
    with PublisherRoot.provision_local_user() as root:
        for invalid in ("", ".", "..", "../escape", "C:\\escape", "CON", "name."):
            with pytest.raises(PublisherRootError):
                root._path_for_display(invalid)


def test_unsafe_posix_ancestor_fails_before_creating_app_directory(
    isolated_profile: Path,
) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode and ACL checks are platform-specific")
    isolated_profile.chmod(0o777)
    try:
        with pytest.raises(PublisherRootError, match="write and traverse"):
            PublisherRoot.provision_local_user()
        assert not (isolated_profile / publisher_root._APP_DIRECTORY).exists()
    finally:
        isolated_profile.chmod(0o700)


def test_existing_profile_with_loose_posix_mode_is_refused(isolated_profile: Path) -> None:
    if os.name != "posix":
        pytest.skip("POSIX mode check is platform-specific")
    with PublisherRoot.provision_local_user() as root:
        profile_path = root.path
    profile_path.chmod(0o750)
    with pytest.raises(PublisherRootError, match="mode 0700"):
        PublisherRoot.open_local_user()


def test_wrong_owner_profile_is_refused(
    isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with PublisherRoot.provision_local_user() as root:
        profile_path = root.path
    monkeypatch.setattr(SecureRoot, "owned_by_current_user", lambda _root: False)
    with pytest.raises(PublisherRootError, match="owner or permissions"):
        PublisherRoot.open_local_user()
    assert profile_path.is_dir()


def test_profile_publish_verify_and_cleanup_use_only_one_name(
    isolated_profile: Path, tmp_path: Path
) -> None:

    dataset = _dataset(tmp_path)
    with PublisherRoot.provision_local_user() as root:
        manifest = publish_dataset.publish_to_root(
            dataset, root, "daily-bundle", teacher="synthetic-test"
        )
        files = manifest["files"]
        assert isinstance(files, dict)
        assert "dataset.jsonl" in files
        assert publish_dataset.verify_from_root(root, "daily-bundle") == []
        with pytest.raises(publish_dataset.PublishError, match="one safe directory name"):
            publish_dataset.publish_to_root(dataset, root, "../outside", teacher="synthetic-test")
        assert not (root.path.parent / "outside").exists()
        assert not list(root.path.glob(".omniagent-publish-*"))


def test_cli_safe_default_publishes_under_the_local_user_profile(
    isolated_profile: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:

    dataset = _dataset(tmp_path)
    assert (
        publish_dataset.main([str(dataset), "--dest", "cli-bundle", "--teacher", "synthetic-test"])
        == 0
    )
    output = capsys.readouterr().out
    assert (
        str(isolated_profile / publisher_root._APP_DIRECTORY / "publish" / "cli-bundle") in output
    )
    with PublisherRoot.open_local_user() as root:
        assert publish_dataset.verify_from_root(root, "cli-bundle") == []


def test_cli_requires_explicit_local_only_path_for_arbitrary_destinations() -> None:

    with pytest.raises(SystemExit):
        publish_dataset.main(["--verify-only", "--dest", "C:/arbitrary/path"])


@pytest.mark.skipif(os.name == "nt", reason="XDG_DATA_HOME is Linux-specific")
def test_xdg_data_home_must_be_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", "relative/path")
    with pytest.raises(PublisherRootError, match="absolute path"):
        publisher_root._known_local_data_root()
