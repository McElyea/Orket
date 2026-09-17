"""Windows target handles and ancestor rename exclusion; owned-thread use only."""

from __future__ import annotations

import ctypes
import os
from contextlib import ExitStack, contextmanager
from ctypes import wintypes
from pathlib import Path

_OPEN_EXISTING, _OPEN_ALWAYS = 3, 4
_READ, _WRITE, _DELETE = 0x80000000, 0x40000000, 0x00010000
_BACKUP_SEMANTICS, _OPEN_REPARSE_POINT = 0x02000000, 0x00200000
_DIRECTORY, _REPARSE_POINT = 0x10, 0x400


class _AttributeTagInfo(ctypes.Structure):
    _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]


def _api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    for name in ("GetFileInformationByHandleEx", "SetFileInformationByHandle"):
        function = getattr(kernel, name)
        function.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        function.restype = wintypes.BOOL
    return kernel


def _close(kernel, handle):
    if not kernel.CloseHandle(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _open(kernel, owned, path, *, access=0, create=False, directory=True):
    # No FILE_SHARE_DELETE: opened ancestors cannot be replaced while descendants open.
    handle = kernel.CreateFileW(str(path), access, 3, None, _OPEN_ALWAYS if create else _OPEN_EXISTING,
                                _BACKUP_SEMANTICS | _OPEN_REPARSE_POINT, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    owned.callback(_close, kernel, handle)
    info = _AttributeTagInfo()
    if not kernel.GetFileInformationByHandleEx(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    if info.attributes & _REPARSE_POINT or bool(info.attributes & _DIRECTORY) != directory:
        raise RuntimeError("E_OUTWARD_BOUND_FILESYSTEM_REPARSE_OR_TYPE_DRIFT")
    return handle


def _delete(kernel, handle):
    # FileDispositionInfo deletes the opened object, without resolving the path again.
    delete_file = wintypes.BOOLEAN(1)
    if not kernel.SetFileInformationByHandle(handle, 4, ctypes.byref(delete_file), ctypes.sizeof(delete_file)):
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def open_target(root: Path, target: Path, requested: Path, *, operation: str):
    import msvcrt

    if len(target.drive) != 2 or target.drive[1] != ":":
        raise RuntimeError("E_OUTWARD_BOUND_FILESYSTEM_LOCAL_DRIVE_REQUIRED")
    kernel = _api()
    with ExitStack() as owned:
        current = Path(target.anchor)
        _open(kernel, owned, current)
        for part in target.parent.parts[1:]:
            current /= part
            if operation in {"write_file", "create_directory"} and current.is_relative_to(root):
                # The handle check below still refuses an existing reparse point.
                current.mkdir(exist_ok=True)
            _open(kernel, owned, current)
        if root.resolve() != root or requested.resolve() != target:
            raise RuntimeError("E_OUTWARD_AUTHORIZATION_TARGET_DRIFT")
        if operation == "create_directory":
            # Existing files/reparse points are refused by the handle check.
            target.mkdir(exist_ok=True)
            _open(kernel, owned, target)
            yield None, None
        elif operation == "delete_file":
            handle = _open(kernel, owned, target, access=_DELETE, directory=False)
            yield None, lambda: _delete(kernel, handle)
        else:
            write = operation == "write_file"
            # A separate stack transfers ownership to the CRT descriptor exactly once.
            with ExitStack() as target_owner:
                handle = _open(kernel, target_owner, target, access=_WRITE if write else _READ,
                               create=write, directory=False)
                descriptor = msvcrt.open_osfhandle(handle, os.O_BINARY | (os.O_WRONLY if write else os.O_RDONLY))
                target_owner.pop_all()
            owned.callback(os.close, descriptor)
            yield descriptor, None
