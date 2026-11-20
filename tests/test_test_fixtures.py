"""Tests for security-sensitive test fixture root selection."""

from __future__ import annotations

import errno
import importlib.util
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest


def _load_test_fixtures() -> ModuleType:
    fixture_path = Path(__file__).with_name("conftest.py")
    spec = importlib.util.spec_from_file_location("_omniagent_test_fixtures", fixture_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load test fixture helpers.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_test_root_falls_back_after_permission_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_module = _load_test_fixtures()
    helper_name = "_create_private_test_root_candidate"
    create_root = cast(
        Callable[[], Path],
        getattr(fixture_module, helper_name),
    )
    unsafe = tmp_path / "unsafe"
    denied = tmp_path / "denied"
    available = tmp_path / "available"
    for candidate in (unsafe, denied, available):
        candidate.mkdir()

    candidates = [unsafe, denied, available]
    monkeypatch.setattr(fixture_module, "_candidate_test_parents", lambda: candidates)
    monkeypatch.setattr(
        fixture_module,
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

    monkeypatch.setattr(tempfile, "mkdtemp", create_temp_directory)
    root = create_root()
    try:
        assert root.parent == available
        assert attempts == [denied, available]
    finally:
        shutil.rmtree(root)


def test_private_test_root_does_not_swallow_unexpected_creation_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture_module = _load_test_fixtures()
    helper_name = "_create_private_test_root_candidate"
    create_root = cast(
        Callable[[], Path],
        getattr(fixture_module, helper_name),
    )
    parent = tmp_path / "safe"
    parent.mkdir()
    monkeypatch.setattr(fixture_module, "_candidate_test_parents", lambda: [parent])
    monkeypatch.setattr(fixture_module, "_supports_private_test_parent", lambda _parent: True)

    def fail_unexpectedly(*, prefix: str, dir: Path) -> str:  # noqa: A002
        _ = prefix, dir
        raise OSError(errno.EIO, "synthetic I/O failure")

    monkeypatch.setattr(tempfile, "mkdtemp", fail_unexpectedly)
    with pytest.raises(OSError, match="synthetic I/O failure") as raised:
        create_root()
    assert raised.value.errno == errno.EIO
