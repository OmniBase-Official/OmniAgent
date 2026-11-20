"""Windows ACL policy tests for safe local-user publisher ancestors."""

from __future__ import annotations

import ctypes
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from publisher_root import _known_local_data_root
from securefs import SecureRoot


def _ctypes_attribute(name: str) -> object:
    return getattr(ctypes, name)


def _load_windows_dll(name: str) -> ctypes.CDLL:
    loader = cast(Callable[..., ctypes.CDLL], _ctypes_attribute("WinDLL"))
    return loader(name, use_last_error=True)


def _windows_error() -> OSError:
    get_last_error = cast(Callable[[], int], _ctypes_attribute("get_last_error"))
    win_error = cast(Callable[[int], OSError], _ctypes_attribute("WinError"))
    return win_error(get_last_error())


def _current_sid() -> str:
    whoami = Path(os.environ["SYSTEMROOT"]) / "System32" / "whoami.exe"
    result = subprocess.run(  # noqa: S603 - fixed Windows executable
        [str(whoami), "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    matches = re.findall(r"S-1-\d+(?:-\d+)+", result.stdout)
    if len(matches) != 1:
        raise AssertionError("could not identify current Windows SID")
    sid = matches[0]
    if not isinstance(sid, str):
        raise TypeError("could not identify current Windows SID")
    return sid


def _set_dacl(path: Path, sddl: str) -> None:
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
        sddl, 1, ctypes.byref(descriptor), None
    ):
        raise _windows_error()
    try:
        if not advapi.SetFileSecurityW(str(path), 0x00000004, descriptor):
            raise _windows_error()
    finally:
        kernel.LocalFree(descriptor)


def _explicit_acl(sid: str, extra_aces: str = "") -> str:
    return "D:P(A;OICI;FA;;;S-1-5-18)(A;OICI;FA;;;S-1-5-32-544)" f"(A;OICI;FA;;;{sid}){extra_aces}"


def _supports_private_staging(path: Path) -> bool:
    root = SecureRoot(path, writable=True, _allow_safe_inherited_ancestors=True)
    try:
        return root.supports_private_staging()
    finally:
        root.close()


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows DACL validation requires Windows")


@pytest.mark.parametrize(
    "rights",
    [
        "0x00000002",  # FILE_ADD_FILE / FILE_WRITE_DATA
        "0x00000004",  # FILE_ADD_SUBDIRECTORY / FILE_APPEND_DATA
        "0x00010000",  # DELETE
        "0x00000040",  # FILE_DELETE_CHILD
        "0x00040000",  # WRITE_DAC
        "0x00080000",  # WRITE_OWNER
        "GW",  # GENERIC_WRITE
        "GA",  # GENERIC_ALL
    ],
)
@pytest.mark.parametrize("sid", ["S-1-5-11", "S-1-1-0", "S-1-5-32-545"])
def test_untrusted_mutation_allow_is_rejected_even_with_deny(
    tmp_path: Path, rights: str, sid: str
) -> None:
    current = _current_sid()
    directory = tmp_path / "unsafe"
    directory.mkdir()
    extra = f"(D;;{rights};;;{sid})(A;;{rights};;;{sid})"
    _set_dacl(directory, _explicit_acl(current, extra))
    assert not _supports_private_staging(directory)


def test_inherited_unsafe_grant_is_checked_at_each_ancestor(tmp_path: Path) -> None:
    current = _current_sid()
    top = tmp_path / "unsafe-parent"
    top.mkdir()
    _set_dacl(top, _explicit_acl(current, "(A;OICI;0x00000040;;;S-1-5-11)"))
    middle = top / "middle"
    leaf = middle / "leaf"
    middle.mkdir()
    leaf.mkdir()
    assert not _supports_private_staging(leaf)


def test_benign_inherited_read_and_traverse_grants_are_accepted(tmp_path: Path) -> None:
    current = _current_sid()
    top = tmp_path / "read-only-parent"
    top.mkdir()
    _set_dacl(top, _explicit_acl(current, "(A;OICI;FRFX;;;S-1-5-11)"))
    middle = top / "middle"
    leaf = middle / "leaf"
    middle.mkdir()
    leaf.mkdir()
    assert _supports_private_staging(leaf)


def test_supported_local_appdata_ancestors_have_a_safe_standard_acl() -> None:
    local_data = _known_local_data_root()
    assert local_data.is_dir()
    root = SecureRoot(local_data, writable=True, _allow_safe_inherited_ancestors=True)
    try:
        assert root.supports_private_staging(), "LocalAppData ACL ancestry is not supported safely"
        assert root.owned_by_current_user()
    finally:
        root.close()
