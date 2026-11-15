"""Handle-relative filesystem access for directories writable by an attacker.

The mount policy is strict: no symbolic links, reparse points, or mounted
filesystems below the pinned root. Linux uses openat2 to enforce that policy;
regular-file names are first pinned with O_PATH and checked before opening the
same object through procfs, so a device node is never opened for I/O. If procfs
is unavailable, access fails closed. Windows uses NtCreateFile relative to
retained directory handles and rejects reparse points after opening them
without following. Other platforms fail closed.
"""

from __future__ import annotations

import ctypes
import errno
import os
import stat
import sys
import weakref
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path


class SecureFSError(OSError):
    """A path could not be accessed under the secure filesystem policy."""


class DirectoryLimitError(SecureFSError):
    """Directory enumeration exceeded its caller-provided bound."""


_DUPLICATE_SAME_ACCESS = 2
_ERROR_HANDLE_EOF = 38
_STATUS_NO_MORE_FILES = 0x80000006
_STATUS_OBJECT_NAME_COLLISION = 0xC0000035
_WINDOWS_DRIVE_COLON_INDEX = 1


def _components(relative: str) -> tuple[str, ...]:
    if not isinstance(relative, str) or "\0" in relative:
        raise SecureFSError(errno.EINVAL, "invalid relative path")
    value = relative.replace("\\", "/")
    if value.startswith("/") or (
        len(value) > _WINDOWS_DRIVE_COLON_INDEX and value[_WINDOWS_DRIVE_COLON_INDEX] == ":"
    ):
        raise SecureFSError(errno.EPERM, "absolute paths are refused")
    parts = tuple(part for part in value.split("/") if part not in {"", "."})
    if any(part == ".." for part in parts):
        raise SecureFSError(errno.EPERM, "parent traversal is refused")
    return parts


if sys.platform == "win32":
    from ctypes import wintypes

    _nt = ctypes.WinDLL("ntdll")
    _k = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi = ctypes.WinDLL("advapi32", use_last_error=True)

    class _US(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class _OA(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(_US)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class _IOSB(ctypes.Structure):
        _fields_ = [
            ("Status", ctypes.c_size_t),
            ("Information", ctypes.c_size_t),
        ]

    class _TAG(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("ReparseTag", wintypes.DWORD),
        ]

    class _STANDARD(ctypes.Structure):
        _fields_ = [
            ("AllocationSize", ctypes.c_longlong),
            ("EndOfFile", ctypes.c_longlong),
            ("NumberOfLinks", wintypes.DWORD),
            ("DeletePending", wintypes.BOOLEAN),
            ("Directory", wintypes.BOOLEAN),
        ]

    _nt.NtCreateFile.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(_OA),
        ctypes.POINTER(_IOSB),
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.ULONG,
        wintypes.LPVOID,
        wintypes.ULONG,
    ]
    _nt.NtCreateFile.restype = ctypes.c_long
    _nt.NtClose.argtypes = [wintypes.HANDLE]
    _nt.NtSetInformationFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_IOSB),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    _nt.NtSetInformationFile.restype = ctypes.c_long
    _nt.NtQueryVolumeInformationFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_IOSB),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    _nt.NtQueryVolumeInformationFile.restype = ctypes.c_long
    _nt.NtQueryDirectoryFile.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.LPVOID,
        ctypes.POINTER(_IOSB),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
        wintypes.BOOLEAN,
        ctypes.POINTER(_US),
        wintypes.BOOLEAN,
    ]
    _nt.NtQueryDirectoryFile.restype = ctypes.c_long
    _k.CreateFileW.restype = wintypes.HANDLE
    _k.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _k.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _k.GetFileInformationByHandleEx.restype = wintypes.BOOL
    _k.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    _k.FlushFileBuffers.restype = wintypes.BOOL
    _k.DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    _k.GetCurrentProcess.restype = wintypes.HANDLE
    _k.LocalFree.argtypes = [wintypes.HLOCAL]
    _advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.ULONG),
    ]
    _advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL

    _INVALID = ctypes.c_void_p(-1).value
    _SHARE = 7
    _SHARE_READ = 1
    _SYNC = 0x00100000
    _READ_DATA = 1
    _READ_ATTR = 0x80
    _OBJ = 0x40 | 0x1000  # case insensitive and don't reparse
    _REPARSE = 0x00200000
    _SYNC_IO = 0x20
    _DIR = 1
    _NONDIR = 0x40
    _FILE_CREATE = 2
    _FILE_DELETE = 0x00010000
    _FILE_ADD_SUBDIRECTORY = 0x4
    _FILE_DELETE_CHILD = 0x40
    _FILE_ATTRIBUTE_DIRECTORY = 0x10
    _FILE_ATTRIBUTE_NORMAL = 0x80
    _FILE_PERSISTENT_ACLS = 0x8

    def _native_handle_value(value: int | None) -> int:
        if value is None:
            raise OSError(errno.EIO, "Windows API returned an empty handle")
        return int(value)

    def _tag(handle: int) -> int:
        info = _TAG()
        if not _k.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if info.FileAttributes & 0x400:
            raise SecureFSError(errno.ELOOP, "reparse point refused")
        return int(info.FileAttributes)

    def _nt_open(
        parent: int,
        name: str,
        directory: bool,
        desired_access: int = _READ_DATA | _READ_ATTR | _SYNC,
        share: int = _SHARE,
    ) -> int:
        if name in {"", ".", ".."} or any(c in name for c in "\\/:\0"):
            raise SecureFSError(errno.EINVAL, "invalid path component")
        buf = ctypes.create_unicode_buffer(name)
        us = _US(len(name) * 2, (len(name) + 1) * 2, ctypes.cast(buf, wintypes.LPWSTR))
        oa = _OA(ctypes.sizeof(_OA), parent, ctypes.pointer(us), _OBJ, None, None)
        iosb, out = _IOSB(), wintypes.HANDLE()
        opts = _REPARSE | _SYNC_IO | (_DIR if directory else _NONDIR)
        status = _nt.NtCreateFile(
            ctypes.byref(out),
            desired_access,
            ctypes.byref(oa),
            ctypes.byref(iosb),
            None,
            0,
            share,
            1,
            opts,
            None,
            0,
        )
        if status < 0:
            raise OSError(
                errno.ENOENT, f"relative open failed (NTSTATUS 0x{status & 0xffffffff:08x})", name
            )
        try:
            handle = _native_handle_value(out.value)
            attrs = _tag(handle)
        except BaseException:
            _nt.NtClose(out)
            raise
        if bool(attrs & 0x10) != directory:
            _nt.NtClose(handle)
            raise SecureFSError(errno.EINVAL, "unexpected filesystem object type")
        return handle

    class SecureRoot:
        """A retained root handle and operations confined beneath it."""

        def __init__(self, root: Path, *, writable: bool = False) -> None:
            absolute = str(root.expanduser().absolute())
            drive, tail = os.path.splitdrive(absolute)
            if not drive or not tail.startswith("\\"):
                raise SecureFSError(errno.ENOTSUP, "workspace must be on a local Windows volume")
            current = _k.CreateFileW(
                drive + "\\", _SYNC | _READ_ATTR, _SHARE, None, 3, 0x02000000, None
            )
            if current == _INVALID or current is None:
                raise ctypes.WinError(ctypes.get_last_error())
            current = int(current)
            root_handle = current
            try:
                parts = [p for p in tail.split("\\") if p]
                for index, part in enumerate(parts):
                    desired = _READ_DATA | _READ_ATTR | _SYNC
                    if writable and index == len(parts) - 1:
                        desired |= _FILE_ADD_SUBDIRECTORY | _FILE_DELETE_CHILD | _FILE_DELETE
                    child = _nt_open(current, part, True, desired)
                    if current != root_handle:
                        _nt.NtClose(current)
                    current = child
                self.handle = current
            except BaseException:
                if current != root_handle:
                    _nt.NtClose(current)
                _k.CloseHandle(root_handle)
                raise
            if current != root_handle:
                _k.CloseHandle(root_handle)
            self._finalizer = weakref.finalize(self, _nt.NtClose, self.handle)

        def open(self, relative: str, *, directory: bool = False, immutable: bool = False) -> int:
            parts = _components(relative)
            if not parts:
                duplicate = wintypes.HANDLE()
                process = _k.GetCurrentProcess()
                if not _k.DuplicateHandle(
                    process,
                    self.handle,
                    process,
                    ctypes.byref(duplicate),
                    0,
                    False,
                    _DUPLICATE_SAME_ACCESS,
                ):
                    raise ctypes.WinError(ctypes.get_last_error())
                return _native_handle_value(duplicate.value)
            owned: list[int] = []
            parent = self.handle
            try:
                for part in parts[:-1]:
                    parent = _nt_open(parent, part, True)
                    owned.append(parent)
                return _nt_open(
                    parent, parts[-1], directory, share=_SHARE_READ if immutable else _SHARE
                )
            finally:
                for handle in reversed(owned):
                    _nt.NtClose(handle)

        def info(self, handle: int) -> tuple[int, int, bool]:
            value = _STANDARD()
            if not _k.GetFileInformationByHandleEx(
                handle, 1, ctypes.byref(value), ctypes.sizeof(value)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            return value.EndOfFile, value.NumberOfLinks, bool(value.Directory)

        def immutable_to_other_users(self, handle: int) -> bool:
            # immutable=True opens the file without sharing writes or deletes.
            _ = handle
            return True

        def read(self, handle: int, limit: int) -> bytes:
            # ReadFile uses the very handle that was inspected above.
            _k.ReadFile.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            _k.ReadFile.restype = wintypes.BOOL
            out = bytearray()
            while len(out) <= limit:
                buf, count = (
                    ctypes.create_string_buffer(min(65536, limit + 1 - len(out))),
                    wintypes.DWORD(),
                )
                if not _k.ReadFile(handle, buf, len(buf), ctypes.byref(count), None):
                    error = ctypes.get_last_error()
                    if error == _ERROR_HANDLE_EOF:
                        break
                    raise ctypes.WinError(error)
                if not count.value:
                    break
                out.extend(buf.raw[: count.value])
            return bytes(out)

        def iter_names(
            self, handle: int, *, max_entries: int
        ) -> Iterator[tuple[str, int, int, bool]]:
            # FileIdBothDirectoryInformation; each batch is bounded to 64 KiB.
            entries_seen = 0
            restart = True
            while True:
                buffer = ctypes.create_string_buffer(65536)
                iosb = _IOSB()
                status = _nt.NtQueryDirectoryFile(
                    handle,
                    None,
                    None,
                    None,
                    ctypes.byref(iosb),
                    buffer,
                    len(buffer),
                    37,
                    False,
                    None,
                    restart,
                )
                restart = False
                if (status & 0xFFFFFFFF) == _STATUS_NO_MORE_FILES:
                    break
                if status < 0:
                    raise OSError(
                        errno.EIO,
                        f"directory enumeration failed (NTSTATUS 0x{status & 0xffffffff:08x})",
                    )
                offset = 0
                while True:
                    base = ctypes.addressof(buffer) + offset
                    next_offset = ctypes.c_uint32.from_address(base).value
                    size = ctypes.c_int64.from_address(base + 40).value
                    attrs = ctypes.c_uint32.from_address(base + 56).value
                    name_len = ctypes.c_uint32.from_address(base + 60).value
                    name = ctypes.wstring_at(base + 104, name_len // 2)
                    if name not in {".", ".."}:
                        entries_seen += 1
                        if entries_seen > max_entries:
                            raise DirectoryLimitError(errno.E2BIG, "directory entry limit exceeded")
                        yield name, size, attrs, bool(attrs & 0x10)
                    if not next_offset:
                        break
                    offset += next_offset

        def iter_chunks(self, handle: int, chunk_size: int = 1 << 20) -> Iterator[bytes]:
            _k.ReadFile.argtypes = [
                wintypes.HANDLE,
                wintypes.LPVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            _k.ReadFile.restype = wintypes.BOOL
            while True:
                buffer, count = ctypes.create_string_buffer(chunk_size), wintypes.DWORD()
                if not _k.ReadFile(handle, buffer, chunk_size, ctypes.byref(count), None):
                    error = ctypes.get_last_error()
                    if error == _ERROR_HANDLE_EOF:
                        return
                    raise ctypes.WinError(error)
                if count.value == 0:
                    return
                yield buffer.raw[: count.value]

        def supports_private_staging(self) -> bool:
            buffer = ctypes.create_string_buffer(1024)
            iosb = _IOSB()
            status = _nt.NtQueryVolumeInformationFile(
                self.handle, ctypes.byref(iosb), buffer, len(buffer), 5
            )
            return status >= 0 and bool(
                ctypes.c_uint32.from_address(ctypes.addressof(buffer)).value & _FILE_PERSISTENT_ACLS
            )

        def create_directory(self, name: str) -> int:
            if not self.supports_private_staging():
                raise SecureFSError(errno.ENOTSUP, "destination filesystem lacks persistent ACLs")
            if len(_components(name)) != 1:
                raise SecureFSError(errno.EINVAL, "staging name must be one component")
            descriptor = wintypes.LPVOID()
            if not _advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                "D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)",
                1,
                ctypes.byref(descriptor),
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                text = ctypes.create_unicode_buffer(name)
                us = _US(len(name) * 2, (len(name) + 1) * 2, ctypes.cast(text, wintypes.LPWSTR))
                oa = _OA(
                    ctypes.sizeof(_OA), self.handle, ctypes.pointer(us), _OBJ, descriptor, None
                )
                iosb, out = _IOSB(), wintypes.HANDLE()
                status = _nt.NtCreateFile(
                    ctypes.byref(out),
                    _FILE_DELETE | _READ_DATA | _READ_ATTR | _SYNC,
                    ctypes.byref(oa),
                    ctypes.byref(iosb),
                    None,
                    _FILE_ATTRIBUTE_DIRECTORY,
                    _SHARE_READ,
                    _FILE_CREATE,
                    _REPARSE | _SYNC_IO | _DIR,
                    None,
                    0,
                )
                if status < 0:
                    raise OSError(
                        errno.EIO,
                        f"private stage create failed (NTSTATUS 0x{status & 0xffffffff:08x})",
                    )
                handle = _native_handle_value(out.value)
                if not (_tag(handle) & _FILE_ATTRIBUTE_DIRECTORY):
                    _nt.NtClose(handle)
                    raise SecureFSError(errno.EINVAL, "staging object is not a directory")
                return handle
            finally:
                _k.LocalFree(descriptor)

        def create_file(self, directory: int, name: str) -> int:
            if len(_components(name)) != 1:
                raise SecureFSError(errno.EINVAL, "staged file name must be one component")
            text = ctypes.create_unicode_buffer(name)
            us = _US(len(name) * 2, (len(name) + 1) * 2, ctypes.cast(text, wintypes.LPWSTR))
            oa = _OA(ctypes.sizeof(_OA), directory, ctypes.pointer(us), _OBJ, None, None)
            iosb, out = _IOSB(), wintypes.HANDLE()
            status = _nt.NtCreateFile(
                ctypes.byref(out),
                _FILE_DELETE | _READ_DATA | 0x2 | _READ_ATTR | _SYNC,
                ctypes.byref(oa),
                ctypes.byref(iosb),
                None,
                _FILE_ATTRIBUTE_NORMAL,
                _SHARE_READ,
                _FILE_CREATE,
                _REPARSE | _SYNC_IO | _NONDIR,
                None,
                0,
            )
            if status < 0:
                raise OSError(
                    errno.EIO, f"staged file create failed (NTSTATUS 0x{status & 0xffffffff:08x})"
                )
            handle = _native_handle_value(out.value)
            _tag(handle)
            return handle

        def open_child(
            self,
            directory: int,
            name: str,
            *,
            directory_entry: bool = False,
            delete: bool = False,
        ) -> int:
            access = _READ_DATA | _READ_ATTR | _SYNC
            if delete:
                access |= _FILE_DELETE
            return _nt_open(directory, name, directory_entry, access)

        def write(self, handle: int, content: bytes) -> None:
            _k.WriteFile.argtypes = [
                wintypes.HANDLE,
                wintypes.LPCVOID,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
                wintypes.LPVOID,
            ]
            _k.WriteFile.restype = wintypes.BOOL
            offset = 0
            while offset < len(content):
                chunk = content[offset : offset + (1 << 20)]
                written = wintypes.DWORD()
                if not _k.WriteFile(handle, chunk, len(chunk), ctypes.byref(written), None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if written.value == 0:
                    raise OSError(errno.EIO, "staged file write made no progress")
                offset += written.value

        def flush(self, handle: int) -> None:
            if not _k.FlushFileBuffers(handle):
                raise ctypes.WinError(ctypes.get_last_error())

        def rename_noreplace(self, handle: int, stage_name: str, name: str) -> None:  # noqa: ARG002 - Windows rename is handle based
            if len(_components(name)) != 1:
                raise SecureFSError(errno.EINVAL, "destination name must be one component")
            encoded = name.encode("utf-16-le")
            info = ctypes.create_string_buffer(20 + len(encoded))
            ctypes.c_void_p.from_buffer(info, 8).value = self.handle
            ctypes.c_uint32.from_buffer(info, 16).value = len(encoded)
            ctypes.memmove(ctypes.addressof(info) + 20, encoded, len(encoded))
            iosb = _IOSB()
            status = _nt.NtSetInformationFile(handle, ctypes.byref(iosb), info, len(info), 10)
            if status < 0:
                error = (
                    errno.EEXIST
                    if (status & 0xFFFFFFFF) == _STATUS_OBJECT_NAME_COLLISION
                    else errno.EIO
                )
                raise OSError(
                    error, f"no-replace promotion failed (NTSTATUS 0x{status & 0xffffffff:08x})"
                )

        def delete_handle(self, handle: int) -> None:
            delete = ctypes.c_ubyte(1)
            iosb = _IOSB()
            status = _nt.NtSetInformationFile(
                handle, ctypes.byref(iosb), ctypes.byref(delete), 1, 13
            )
            if status < 0:
                raise OSError(
                    errno.EIO, f"handle cleanup failed (NTSTATUS 0x{status & 0xffffffff:08x})"
                )

        def delete_child(self, directory: int, name: str, *, directory_entry: bool = False) -> None:
            handle = self.open_child(directory, name, directory_entry=directory_entry, delete=True)
            try:
                self.delete_handle(handle)
            finally:
                self.close_handle(handle)

        def seek_start(self, handle: int) -> None:
            # FILE_POSITION_INFORMATION, class 14.
            position = ctypes.c_longlong(0)
            iosb = _IOSB()
            status = _nt.NtSetInformationFile(
                handle, ctypes.byref(iosb), ctypes.byref(position), ctypes.sizeof(position), 14
            )
            if status < 0:
                raise OSError(
                    errno.EIO,
                    f"could not rewind staged file (NTSTATUS 0x{status & 0xffffffff:08x})",
                )

        def remove_directory(self, handle: int, name: str) -> None:
            _ = name  # Windows deletion is applied to the pinned directory handle.
            self.delete_handle(handle)

        def close_handle(self, handle: int) -> None:
            _nt.NtClose(handle)

        def close(self) -> None:
            self._finalizer()


else:

    class SecureRoot:
        """Linux openat2 root enforcing BENEATH, no links and no mount crossing."""

        def __init__(self, root: Path, *, writable: bool = False) -> None:
            _ = writable  # POSIX directories are opened read-only; relative mutation uses dir_fd.
            if not sys.platform.startswith("linux"):
                raise SecureFSError(errno.ENOTSUP, "secure handle-relative access unavailable")
            root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            absolute = str(root.expanduser().absolute()).lstrip("/")
            try:
                self.fd = (
                    self._openat2(root_fd, absolute, directory=True, no_xdev=False)
                    if absolute
                    else root_fd
                )
            except BaseException:
                os.close(root_fd)
                raise
            if self.fd != root_fd:
                os.close(root_fd)
            self._finalizer = weakref.finalize(self, os.close, self.fd)

        @staticmethod
        def _openat2(
            parent: int,
            path: str,
            *,
            directory: bool = False,
            no_xdev: bool = True,
            flags: int | None = None,
        ) -> int:
            class _How(ctypes.Structure):
                _fields_ = (
                    ("flags", ctypes.c_uint64),
                    ("mode", ctypes.c_uint64),
                    ("resolve", ctypes.c_uint64),
                )

            resolve = 0x08 | 0x04 | 0x02 | (0x01 if no_xdev else 0)
            how = _How(
                flags
                if flags is not None
                else os.O_RDONLY
                | os.O_CLOEXEC
                | os.O_NONBLOCK
                | (os.O_DIRECTORY if directory else 0),
                0,
                resolve,
            )
            libc = ctypes.CDLL(None, use_errno=True)
            result = libc.syscall(
                437, parent, os.fsencode(path), ctypes.byref(how), ctypes.sizeof(how)
            )
            if result < 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), path)
            return int(result)

        def open(self, relative: str, *, directory: bool = False, immutable: bool = False) -> int:
            parts = _components(relative)
            if not parts:
                return os.dup(self.fd)
            path = "/".join(parts)
            _ = immutable
            if directory:
                return self._openat2(self.fd, path, directory=True)
            # O_PATH pins the name without invoking a device driver. Reopening
            # through this process's fd link obtains a readable handle to that
            # same inode; if procfs is unavailable, fail closed.
            path_handle = self._openat2(
                self.fd,
                path,
                flags=getattr(os, "O_PATH", 0x200000) | os.O_CLOEXEC,
            )
            try:
                pinned = os.fstat(path_handle)
                if not stat.S_ISREG(pinned.st_mode):
                    raise SecureFSError(errno.EPERM, "device nodes and special files are refused")
                try:
                    readable = os.open(
                        f"/proc/self/fd/{path_handle}",
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK,
                    )
                except OSError as exc:
                    raise SecureFSError(
                        errno.ENOTSUP, "procfs handle reopening is unavailable; refusing access"
                    ) from exc
                opened = os.fstat(readable)
                if (opened.st_dev, opened.st_ino) != (pinned.st_dev, pinned.st_ino):
                    os.close(readable)
                    raise SecureFSError(
                        errno.ESTALE, "opened object changed during handle conversion"
                    )
                return readable
            finally:
                os.close(path_handle)

        def info(self, handle: int) -> tuple[int, int, bool]:
            metadata = os.fstat(handle)
            if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
                raise SecureFSError(errno.EPERM, "device nodes and special files are refused")
            return metadata.st_size, metadata.st_nlink, stat.S_ISDIR(metadata.st_mode)

        def immutable_to_other_users(self, handle: int) -> bool:
            metadata = os.fstat(handle)
            mode = stat.S_IMODE(metadata.st_mode)
            owner_write_is_external = metadata.st_uid != os.geteuid() and bool(mode & stat.S_IWUSR)
            group_or_other_write = bool(mode & (stat.S_IWGRP | stat.S_IWOTH))
            return not (owner_write_is_external or group_or_other_write)

        def read(self, handle: int, limit: int) -> bytes:
            chunks = bytearray()
            while len(chunks) <= limit:
                block = os.read(handle, min(65536, limit + 1 - len(chunks)))
                if not block:
                    break
                chunks.extend(block)
            return bytes(chunks)

        def iter_names(
            self, handle: int, *, max_entries: int
        ) -> Iterator[tuple[str, int, int, bool]]:
            entries_seen = 0
            with os.scandir(handle) as entries:
                for entry in entries:
                    entries_seen += 1
                    if entries_seen > max_entries:
                        raise DirectoryLimitError(errno.E2BIG, "directory entry limit exceeded")
                    try:
                        child = self._openat2(
                            handle,
                            entry.name,
                            flags=getattr(os, "O_PATH", 0x200000) | os.O_CLOEXEC,
                        )
                    except OSError:
                        continue
                    try:
                        metadata = os.fstat(child)
                        is_dir = stat.S_ISDIR(metadata.st_mode)
                        if is_dir or stat.S_ISREG(metadata.st_mode):
                            yield entry.name, metadata.st_size, 0, is_dir
                    finally:
                        os.close(child)

        def iter_chunks(self, handle: int, chunk_size: int = 1 << 20) -> Iterator[bytes]:
            while chunk := os.read(handle, chunk_size):
                yield chunk

        def supports_private_staging(self) -> bool:
            metadata = os.fstat(self.fd)
            mode = stat.S_IMODE(metadata.st_mode)
            sticky = bool(mode & stat.S_ISVTX)
            return not (mode & 0o022) or sticky

        def create_directory(self, name: str) -> int:
            if len(_components(name)) != 1:
                raise SecureFSError(errno.EINVAL, "staging name must be one component")
            if not self.supports_private_staging():
                raise SecureFSError(
                    errno.ENOTSUP, "destination parent is writable by other identities"
                )
            os.mkdir(name, 0o700, dir_fd=self.fd)  # parent dir_fd is pinned
            try:
                handle = self.open(name, directory=True)
                mode = stat.S_IMODE(os.fstat(handle).st_mode)
                if mode & 0o077:
                    os.close(handle)
                    os.rmdir(name, dir_fd=self.fd)  # parent dir_fd is pinned
                    raise SecureFSError(  # noqa: TRY301 - staging must be removed on failure
                        errno.ENOTSUP, "filesystem did not enforce private staging mode"
                    )
            except BaseException:
                with suppress(OSError):
                    os.rmdir(name, dir_fd=self.fd)  # pinned parent dir_fd
                raise
            else:
                return handle

        def create_file(self, directory: int, name: str) -> int:
            if len(_components(name)) != 1:
                raise SecureFSError(errno.EINVAL, "staged file name must be one component")
            return os.open(
                name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                0o600,
                dir_fd=directory,
            )

        def open_child(self, directory: int, name: str, *, directory_entry: bool = False) -> int:
            parts = _components(name)
            if len(parts) != 1:
                raise SecureFSError(errno.EINVAL, "child name must be one component")
            if directory_entry:
                return self._openat2(directory, name, directory=True)
            path_handle = self._openat2(
                directory,
                name,
                flags=getattr(os, "O_PATH", 0x200000) | os.O_CLOEXEC,
            )
            try:
                pinned = os.fstat(path_handle)
                if not stat.S_ISREG(pinned.st_mode):
                    raise SecureFSError(errno.EPERM, "device nodes and special files are refused")
                try:
                    readable = os.open(
                        f"/proc/self/fd/{path_handle}",
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NONBLOCK,
                    )
                except OSError as exc:
                    raise SecureFSError(
                        errno.ENOTSUP, "procfs handle reopening is unavailable"
                    ) from exc
                opened = os.fstat(readable)
                if (opened.st_dev, opened.st_ino) != (pinned.st_dev, pinned.st_ino):
                    os.close(readable)
                    raise SecureFSError(
                        errno.ESTALE, "opened object changed during handle conversion"
                    )
                return readable
            finally:
                os.close(path_handle)

        def write(self, handle: int, content: bytes) -> None:
            view = memoryview(content)
            while view:
                written = os.write(handle, view)
                if not written:
                    raise OSError(errno.EIO, "staged file write made no progress")
                view = view[written:]

        def flush(self, handle: int) -> None:
            os.fsync(handle)

        def rename_noreplace(self, handle: int, stage_name: str, name: str) -> None:
            source = self.open(stage_name, directory=True)
            try:
                source_stat, pinned_stat = os.fstat(source), os.fstat(handle)
                if (source_stat.st_dev, source_stat.st_ino) != (
                    pinned_stat.st_dev,
                    pinned_stat.st_ino,
                ):
                    raise SecureFSError(
                        errno.ESTALE, "staging name no longer refers to its pinned handle"
                    )
            finally:
                os.close(source)
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise SecureFSError(errno.ENOTSUP, "atomic no-replace directory rename unavailable")
            result = renameat2(self.fd, os.fsencode(stage_name), self.fd, os.fsencode(name), 1)
            if result != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), name)
            destination = self.open(name, directory=True)
            try:
                destination_stat, pinned_stat = os.fstat(destination), os.fstat(handle)
                if (destination_stat.st_dev, destination_stat.st_ino) != (
                    pinned_stat.st_dev,
                    pinned_stat.st_ino,
                ):
                    raise SecureFSError(
                        errno.ESTALE, "promoted directory differs from pinned staging handle"
                    )
            finally:
                os.close(destination)

        def rename_exchange(self, handle: int, stage_name: str, name: str, expected: int) -> None:
            source = self.open(stage_name, directory=True)
            try:
                source_stat, pinned_stat = os.fstat(source), os.fstat(handle)
                if (source_stat.st_dev, source_stat.st_ino) != (
                    pinned_stat.st_dev,
                    pinned_stat.st_ino,
                ):
                    raise SecureFSError(errno.ESTALE, "staging name changed before exchange")
            finally:
                os.close(source)
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise SecureFSError(errno.ENOTSUP, "atomic directory exchange unavailable")
            result = renameat2(self.fd, os.fsencode(stage_name), self.fd, os.fsencode(name), 2)
            if result != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error), name)
            destination = self.open(name, directory=True)
            try:
                destination_stat, pinned_stat = os.fstat(destination), os.fstat(handle)
                if (destination_stat.st_dev, destination_stat.st_ino) != (
                    pinned_stat.st_dev,
                    pinned_stat.st_ino,
                ):
                    raise SecureFSError(
                        errno.ESTALE, "exchanged destination differs from staging handle"
                    )
            finally:
                os.close(destination)
            old_target = self.open(stage_name, directory=True)
            try:
                target_stat, expected_stat = os.fstat(old_target), os.fstat(expected)
                if (target_stat.st_dev, target_stat.st_ino) != (
                    expected_stat.st_dev,
                    expected_stat.st_ino,
                ):
                    libc.renameat2(self.fd, os.fsencode(stage_name), self.fd, os.fsencode(name), 2)
                    raise SecureFSError(errno.ESTALE, "destination changed during atomic exchange")
            finally:
                os.close(old_target)

        def unlink_child(self, directory: int, name: str) -> None:
            os.unlink(name, dir_fd=directory)  # child dir_fd is pinned

        def delete_child(self, directory: int, name: str, *, directory_entry: bool = False) -> None:
            if directory_entry:
                os.rmdir(name, dir_fd=directory)  # child dir_fd is pinned
            else:
                os.unlink(name, dir_fd=directory)  # child dir_fd is pinned

        def seek_start(self, handle: int) -> None:
            os.lseek(handle, 0, os.SEEK_SET)

        def remove_directory(self, handle: int, name: str) -> None:
            current = self.open(name, directory=True)
            try:
                current_stat, expected_stat = os.fstat(current), os.fstat(handle)
                if (current_stat.st_dev, current_stat.st_ino) != (
                    expected_stat.st_dev,
                    expected_stat.st_ino,
                ):
                    raise SecureFSError(
                        errno.ESTALE, "staging directory name no longer matches its handle"
                    )
            finally:
                os.close(current)
            os.rmdir(name, dir_fd=self.fd)  # parent dir_fd is pinned

        def close_handle(self, handle: int) -> None:
            os.close(handle)

        def close(self) -> None:
            self._finalizer()


__all__ = ["DirectoryLimitError", "SecureFSError", "SecureRoot", "os"]
