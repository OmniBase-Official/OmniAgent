"""Single-user publication capability rooted in the current user's data directory.

This profile protects against other local identities. Processes running as the
same user are trusted and are not isolated from one another.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import struct
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from securefs import SecureRoot

_APP_DIRECTORY = "OmniAgent" if sys.platform == "win32" else "omniagent"
_PUBLISH_DIRECTORY = "publish"
_ACL_ACCESS_XATTR = "system.posix_acl_access"
_ACL_DEFAULT_XATTR = "system.posix_acl_default"
_ACL_VERSION = 2
_ACL_USER_OBJ = 0x01
_ACL_USER = 0x02
_ACL_GROUP_OBJ = 0x04
_ACL_GROUP = 0x08
_ACL_MASK = 0x10
_ACL_OTHER = 0x20
_ACL_WRITE_EXECUTE = 0x06
_WINDOWS_TOKEN_PRIVILEGE_HEADER_BYTES = 4
_WINDOWS_MAX_TOKEN_PRIVILEGE_BYTES = 65536
_POSIX_ACL_UNDEFINED_ID = 0xFFFFFFFF
_POSIX_OWNER_WRITE_TRAVERSE = 0o300
_POSIX_GROUP_WRITE_TRAVERSE = 0o030
_POSIX_OTHER_WRITE_TRAVERSE = 0o003
_WINDOWS_RESERVED = {
    "aux",
    "con",
    "conin$",
    "conout$",
    "nul",
    "prn",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
    *(f"com{number}" for number in "¹²³"),
    *(f"lpt{number}" for number in "¹²³"),
}


class PublisherRootError(OSError):
    """The current user's publication directory is unsafe or unavailable."""


def _load_windows_dll(name: str) -> ctypes.CDLL:
    loader_name = "WinDLL"
    loader = cast(Callable[..., ctypes.CDLL], getattr(ctypes, loader_name))
    return loader(name, use_last_error=True)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _known_local_data_root() -> Path:
    if sys.platform == "win32":

        class _Guid(ctypes.Structure):
            _fields_ = (
                ("data1", ctypes.c_uint32),
                ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16),
                ("data4", ctypes.c_ubyte * 8),
            )

        folder_id = _Guid(
            0xF1B32785,
            0x6FBA,
            0x4FCF,
            (ctypes.c_ubyte * 8)(0x9D, 0x55, 0x7B, 0x8E, 0x7F, 0x15, 0x70, 0x91),
        )
        shell = _load_windows_dll("shell32")
        ole = _load_windows_dll("ole32")
        shell.SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(_Guid),
            ctypes.c_uint32,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_wchar_p),
        ]
        shell.SHGetKnownFolderPath.restype = ctypes.c_long
        ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        result = ctypes.c_wchar_p()
        status = shell.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
        if status < 0 or not result.value:
            raise PublisherRootError(errno.EIO, "could not resolve Windows LocalAppData")
        try:
            return Path(result.value)
        finally:
            ole.CoTaskMemFree(ctypes.cast(result, ctypes.c_void_p))

    if sys.platform.startswith("linux"):
        configured = os.environ.get("XDG_DATA_HOME")
        base = Path(configured) if configured else Path.home() / ".local" / "share"
        if not base.is_absolute():
            raise PublisherRootError(errno.EINVAL, "XDG_DATA_HOME must be an absolute path")
        return base
    raise PublisherRootError(errno.ENOTSUP, "safe publisher profile supports Windows and Linux")


def _windows_standard_token() -> bool:  # noqa: PLR0912, PLR0915 - explicit token privilege checks
    if not _is_windows():
        return True
    advapi = _load_windows_dll("advapi32")
    kernel = _load_windows_dll("kernel32")
    advapi.OpenProcessToken.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi.OpenProcessToken.restype = ctypes.c_int
    advapi.GetTokenInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    advapi.GetTokenInformation.restype = ctypes.c_int
    advapi.LookupPrivilegeValueW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    advapi.LookupPrivilegeValueW.restype = ctypes.c_int
    advapi.CheckTokenMembership.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    advapi.CheckTokenMembership.restype = ctypes.c_int
    advapi.ConvertStringSidToSidW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    advapi.ConvertStringSidToSidW.restype = ctypes.c_int
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p

    class _Luid(ctypes.Structure):
        _fields_ = (("low_part", ctypes.c_uint32), ("high_part", ctypes.c_int32))

    token = ctypes.c_void_p()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise PublisherRootError(errno.EACCES, "could not inspect the Windows security token")
    try:
        required = ctypes.c_uint32()
        advapi.GetTokenInformation(token, 3, None, 0, ctypes.byref(required))
        if (
            not _WINDOWS_TOKEN_PRIVILEGE_HEADER_BYTES
            <= required.value
            <= _WINDOWS_MAX_TOKEN_PRIVILEGE_BYTES
        ):
            raise PublisherRootError(errno.EIO, "invalid Windows token privilege data")
        privilege_data = ctypes.create_string_buffer(required.value)
        if not advapi.GetTokenInformation(
            token, 3, privilege_data, len(privilege_data), ctypes.byref(required)
        ):
            raise PublisherRootError(errno.EACCES, "could not inspect Windows token privileges")
        count = ctypes.c_uint32.from_buffer(privilege_data).value
        if 4 + count * 12 > len(privilege_data):
            raise PublisherRootError(errno.EIO, "malformed Windows token privilege data")
        sensitive = ("SeBackupPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege")
        for name in sensitive:
            luid = _Luid()
            if not advapi.LookupPrivilegeValueW(None, name, ctypes.byref(luid)):
                raise PublisherRootError(
                    errno.EACCES, "could not resolve a Windows token privilege"
                )
            expected = bytes(luid)
            for index in range(count):
                offset = 4 + index * 12
                actual = privilege_data.raw[offset : offset + 8]
                attributes = struct.unpack_from("<I", privilege_data.raw, offset + 8)[0]
                if actual == expected and attributes & 0x00000002:
                    return False

        admin_sids = (
            "S-1-5-32-544",
            "S-1-5-32-547",
            "S-1-5-32-548",
            "S-1-5-32-549",
            "S-1-5-32-550",
            "S-1-5-32-551",
            "S-1-5-32-552",
            "S-1-5-32-569",
        )
        for value in admin_sids:
            sid = ctypes.c_void_p()
            if not advapi.ConvertStringSidToSidW(value, ctypes.byref(sid)):
                raise PublisherRootError(errno.EACCES, "could not inspect Windows token groups")
            try:
                member = ctypes.c_int()
                if not advapi.CheckTokenMembership(token, sid, ctypes.byref(member)):
                    raise PublisherRootError(errno.EACCES, "could not inspect Windows token groups")
                if member.value:
                    return False
            finally:
                kernel.LocalFree(sid)
        return True
    finally:
        kernel.CloseHandle(token)


def _acl_entries(path: Path, attribute: str) -> list[tuple[int, int, int]] | None:
    try:
        raw = os.getxattr(path, attribute, follow_symlinks=False)
    except OSError as exc:
        if exc.errno in {
            getattr(errno, "ENODATA", 61),
            getattr(errno, "ENOATTR", 93),
            errno.ENOTSUP,
            getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
        }:
            return None
        raise PublisherRootError(errno.EACCES, "could not inspect POSIX access ACL") from exc
    if (
        len(raw) < _WINDOWS_TOKEN_PRIVILEGE_HEADER_BYTES
        or (len(raw) - _WINDOWS_TOKEN_PRIVILEGE_HEADER_BYTES) % 8
    ):
        raise PublisherRootError(errno.EINVAL, "unsupported POSIX ACL encoding")
    version = struct.unpack_from("<I", raw)[0]
    if version != _ACL_VERSION:
        raise PublisherRootError(errno.ENOTSUP, "unsupported POSIX ACL version")
    entries = [struct.unpack_from("<HHI", raw, offset) for offset in range(4, len(raw), 8)]
    seen: set[int] = set()
    named = False
    for tag, permissions, identifier in entries:
        if permissions & ~0x07 or tag not in {
            _ACL_USER_OBJ,
            _ACL_USER,
            _ACL_GROUP_OBJ,
            _ACL_GROUP,
            _ACL_MASK,
            _ACL_OTHER,
        }:
            raise PublisherRootError(errno.ENOTSUP, "unsupported POSIX ACL entry")
        if tag in {_ACL_USER, _ACL_GROUP}:
            named = True
            if identifier == _POSIX_ACL_UNDEFINED_ID:
                raise PublisherRootError(errno.EINVAL, "malformed POSIX ACL identity")
        elif identifier != _POSIX_ACL_UNDEFINED_ID:
            raise PublisherRootError(errno.EINVAL, "malformed POSIX ACL base entry")
        if tag in {_ACL_USER_OBJ, _ACL_GROUP_OBJ, _ACL_MASK, _ACL_OTHER}:
            if tag in seen:
                raise PublisherRootError(errno.EINVAL, "duplicate POSIX ACL entry")
            seen.add(tag)
    required = {_ACL_USER_OBJ, _ACL_GROUP_OBJ, _ACL_OTHER}
    if not required.issubset(seen) or (named and _ACL_MASK not in seen):
        raise PublisherRootError(errno.EINVAL, "incomplete POSIX ACL")
    return entries


def _acl_has_foreign_write_execute(path: Path, attribute: str) -> bool:
    entries = _acl_entries(path, attribute)
    if entries is None:
        return False
    owner_uid = path.stat(follow_symlinks=False).st_uid
    current_uid = os.geteuid()
    mask = 0x07
    for tag, permissions, _identifier in entries:
        if tag == _ACL_MASK:
            mask = permissions
            break
    for tag, permissions, identifier in entries:
        effective = permissions if tag in {_ACL_USER_OBJ, _ACL_OTHER} else permissions & mask
        if effective & _ACL_WRITE_EXECUTE != _ACL_WRITE_EXECUTE:
            continue
        if tag == _ACL_USER_OBJ:
            if owner_uid != current_uid:
                return True
        elif tag == _ACL_USER:
            if identifier != current_uid:
                return True
        elif tag in {_ACL_GROUP_OBJ, _ACL_GROUP, _ACL_OTHER}:
            # A group may contain another local identity; do not infer that it
            # is private from the current process's supplementary groups.
            return True
        else:
            raise PublisherRootError(errno.ENOTSUP, "unsupported POSIX ACL entry")
    return False


def _validate_posix_ancestors(path: Path) -> None:
    current_uid = os.geteuid()
    for directory in (path, *path.parents):
        try:
            info = directory.stat(follow_symlinks=False)
        except OSError as exc:
            raise PublisherRootError(
                errno.EACCES, "could not inspect publisher path ancestry"
            ) from exc
        if not stat.S_ISDIR(info.st_mode) or directory.is_symlink():
            raise PublisherRootError(
                errno.ELOOP, "publisher path contains a symlink or non-directory"
            )
        mode = info.st_mode
        # Root-owned system ancestors such as / and /home are trusted OS
        # boundaries. Their owner bits do not grant access to this caller;
        # an unprivileged foreign owner with write+traverse remains unsafe.
        if (
            info.st_uid not in {0, current_uid}
            and mode & _POSIX_OWNER_WRITE_TRAVERSE == _POSIX_OWNER_WRITE_TRAVERSE
        ):
            raise PublisherRootError(
                errno.EPERM, "foreign owner can write and traverse a publisher ancestor"
            )
        if (
            mode & _POSIX_GROUP_WRITE_TRAVERSE == _POSIX_GROUP_WRITE_TRAVERSE
            or mode & _POSIX_OTHER_WRITE_TRAVERSE == _POSIX_OTHER_WRITE_TRAVERSE
        ):
            raise PublisherRootError(
                errno.EPERM, "foreign group or users can write and traverse a publisher ancestor"
            )
        if _acl_has_foreign_write_execute(directory, _ACL_ACCESS_XATTR):
            raise PublisherRootError(
                errno.EPERM, "POSIX ACL grants a foreign identity write and traverse access"
            )
        if _acl_has_foreign_write_execute(directory, _ACL_DEFAULT_XATTR):
            raise PublisherRootError(
                errno.EPERM, "default POSIX ACL grants foreign write and traverse access"
            )


class PublisherRoot:
    """An owned, pinned capability for publishing under one local-user root."""

    def __init__(self, root: SecureRoot, path: Path) -> None:
        self._root = root
        self.path = path

    @classmethod
    def provision_local_user(cls) -> PublisherRoot:
        """Create the app-owned profile below the operating system data folder."""
        if not _windows_standard_token():
            raise PublisherRootError(
                errno.EPERM, "publisher requires a standard non-privileged token"
            )
        base = _known_local_data_root()
        if not base.is_dir() or base.is_symlink():
            raise PublisherRootError(
                errno.ENOENT,
                "local data directory must already exist; create it using your OS account",
            )
        if sys.platform.startswith("linux"):
            _validate_posix_ancestors(base)
        try:
            parent = SecureRoot(
                base,
                writable=True,
                _allow_safe_inherited_ancestors=sys.platform == "win32",
            )
        except OSError as exc:
            raise PublisherRootError(
                errno.EACCES, "could not pin the local data directory"
            ) from exc
        try:
            if not parent.supports_private_staging():
                raise PublisherRootError(
                    errno.EPERM, "local data directory ancestry is not private"
                )
            try:
                app_handle = parent.open(_APP_DIRECTORY, directory=True)
            except FileNotFoundError:
                app_handle = parent.create_directory(_APP_DIRECTORY)
            parent.close_handle(app_handle)
        finally:
            parent.close()
        app_path = base / _APP_DIRECTORY
        if sys.platform.startswith("linux"):
            _validate_posix_ancestors(app_path)
        try:
            app_root = SecureRoot(
                app_path,
                writable=True,
                _allow_safe_inherited_ancestors=sys.platform == "win32",
            )
        except OSError as exc:
            raise PublisherRootError(
                errno.EACCES, "could not pin the application data directory"
            ) from exc
        try:
            if not app_root.supports_private_staging():
                raise PublisherRootError(errno.EPERM, "application data directory ACL is unsafe")
            try:
                publish_handle = app_root.open(_PUBLISH_DIRECTORY, directory=True)
            except FileNotFoundError:
                publish_handle = app_root.create_directory(_PUBLISH_DIRECTORY)
            app_root.close_handle(publish_handle)
        finally:
            app_root.close()
        return cls.open_local_user()

    @classmethod
    def open_local_user(cls) -> PublisherRoot:
        """Open and validate an existing local-user publication profile."""
        if not _windows_standard_token():
            raise PublisherRootError(
                errno.EPERM, "publisher requires a standard non-privileged token"
            )
        base = _known_local_data_root()
        path = base / _APP_DIRECTORY / _PUBLISH_DIRECTORY
        if sys.platform.startswith("linux"):
            _validate_posix_ancestors(path)
        try:
            root = SecureRoot(
                path,
                writable=True,
                _allow_safe_inherited_ancestors=sys.platform == "win32",
            )
        except OSError as exc:
            raise PublisherRootError(
                errno.EACCES, "could not safely open the publisher profile"
            ) from exc
        try:
            if not root.supports_private_staging() or not root.owned_by_current_user():
                raise PublisherRootError(  # noqa: TRY301 - close the pinned handle before refusing
                    errno.EPERM, "publisher profile owner or permissions are unsafe"
                )
            if sys.platform.startswith("linux"):
                info = os.fstat(root.fd)
                if info.st_uid != os.geteuid() or info.st_mode & 0o077:
                    raise PublisherRootError(  # noqa: TRY301 - close the pinned handle before refusing
                        errno.EPERM, "publisher profile must be owned by you with mode 0700"
                    )
                if _acl_has_foreign_write_execute(path, _ACL_ACCESS_XATTR):
                    raise PublisherRootError(  # noqa: TRY301 - close the pinned handle before refusing
                        errno.EPERM, "publisher profile ACL is unsafe"
                    )
        except BaseException:
            root.close()
            raise
        return cls(root, path)

    def close(self) -> None:
        self._root.close()

    def __enter__(self) -> PublisherRoot:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _validate_destination_name(self, name: str) -> None:
        if (
            not isinstance(name, str)
            or not name
            or name in {".", ".."}
            or any(character in name for character in "/\\:\0")
            or name.endswith((".", " "))
        ):
            raise PublisherRootError(errno.EINVAL, "destination must be one safe directory name")
        device_name = name.split(".", maxsplit=1)[0].rstrip(" .").casefold()
        if device_name in _WINDOWS_RESERVED:
            raise PublisherRootError(errno.EINVAL, "destination uses a reserved device name")

    def _path_for_display(self, name: str) -> Path:
        self._validate_destination_name(name)
        return self.path / name

    def _secure_root(self) -> SecureRoot:
        return self._root
