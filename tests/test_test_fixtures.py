"""Tests for security-sensitive test fixture root selection."""

from __future__ import annotations

import errno
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import conftest as test_fixtures


def test_private_test_root_falls_back_after_permission_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unsafe = tmp_path / "unsafe"
    denied = tmp_path / "denied"
    available = tmp_path / "available"
    for candidate in (unsafe, denied, available):
        candidate.mkdir()

    candidates = [unsafe, denied, available]
    monkeypatch.setattr(test_fixtures, "_candidate_test_parents", lambda: candidates)
    monkeypatch.setattr(
        test_fixtures,
        "_supports_private_test_parent",
        lambda candidate: candidate != unsafe,
    )
    original_mkdtemp = tempfile.mkdtemp
    attempts: list[Path] = []

    def create_temp_directory(*, prefix: str, dir: Path) -> str:  # noqa: A002
        attempts.append(dir)
        if dir == denied:
            raise PermissionError(errno.EACCES, "synthetic access denied")
        return original_mkdtemp(prefix=prefix, dir=dir)

    monkeypatch.setattr(test_fixtures.tempfile, "mkdtemp", create_temp_directory)
    root = test_fixtures._create_private_test_root_candidate()
    try:
        assert root.parent == available
        assert attempts == [denied, available]
    finally:
        shutil.rmtree(root)


def test_private_test_root_does_not_swallow_unexpected_creation_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "safe"
    parent.mkdir()
    monkeypatch.setattr(test_fixtures, "_candidate_test_parents", lambda: [parent])
    monkeypatch.setattr(test_fixtures, "_supports_private_test_parent", lambda _parent: True)

    def fail_unexpectedly(*, prefix: str, dir: Path) -> str:  # noqa: A002
        _ = prefix, dir
        raise OSError(errno.EIO, "synthetic I/O failure")

    monkeypatch.setattr(test_fixtures.tempfile, "mkdtemp", fail_unexpectedly)
    with pytest.raises(OSError, match="synthetic I/O failure") as raised:
        test_fixtures._create_private_test_root_candidate()
    assert raised.value.errno == errno.EIO
