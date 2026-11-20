"""Shared fixtures for tests that exercise explicit workspace behavior."""

from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast

import pytest

import publisher_root
from sandbox import Workspace, workspace_scope
from securefs import SecureRoot


def _load_windows_dll(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, "WinDLL"))  # noqa: B009 - ctypes.WinDLL is absent from non-Windows stubs
    return loader(name, use_last_error=True)


def _protect_owner_private_test_directory(path: Path) -> None:
    advapi = _load_windows_dll("advapi32")
    kernel = _load_windows_dll("kernel32")
    descriptor = ctypes.c_void_p()
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
    ]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = ctypes.c_int
    advapi.SetFileSecurityW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_void_p]
    advapi.SetFileSecurityW.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        "D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)",
        1,
        ctypes.byref(descriptor),
        None,
    ):
        raise RuntimeError("Could not prepare an owner-private Windows test directory.")
    try:
        if not advapi.SetFileSecurityW(str(path), 0x00000004, descriptor):
            raise RuntimeError("Could not prepare an owner-private Windows test directory.")
    finally:
        kernel.LocalFree(descriptor)


@pytest.fixture(autouse=True)
def explicit_repository_workspace() -> Iterator[None]:
    """Give legacy tests an explicit root instead of relying on CWD fallback."""
    with workspace_scope(Workspace.at(Path.cwd())):
        yield


@pytest.fixture
def owner_private_test_root() -> Iterator[Path]:
    """Create a test root and verify its ancestry under the production policy."""
    if os.name == "nt":
        parent = Path(os.environ.get("USERPROFILE") or Path.home())
    else:
        parent = Path(os.environ.get("RUNNER_TEMP") or tempfile.gettempdir())
    root = Path(tempfile.mkdtemp(prefix=f"omniagent-test-{uuid.uuid4().hex}-", dir=parent))
    try:
        if os.name == "nt":
            _protect_owner_private_test_directory(root)
            secure_root = SecureRoot(
                root, writable=True, _allow_safe_inherited_ancestors=True
            )
            try:
                if not secure_root.supports_private_staging():
                    raise RuntimeError("Runner ancestry does not support private test staging.")
            finally:
                secure_root.close()
        elif sys.platform.startswith("linux"):
            root.chmod(0o700)
            publisher_root._validate_posix_ancestors(root)
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)
