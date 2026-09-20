"""Native file-publication refusal controls for the two admitted proof hosts."""
import os
import stat
from contextlib import contextmanager


@contextmanager
def deny_catalog_replace(path):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.CloseHandle.restype = wintypes.BOOL
        handle = api.CreateFileW(str(path), 0x80000000, 3, None, 3, 0x80, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            yield
        finally:
            if not api.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
    elif os.name == "posix":
        original = stat.S_IMODE(path.parent.stat().st_mode)
        path.parent.chmod(0o555)
        try:
            yield
        finally:
            path.parent.chmod(original)
    else:
        raise AssertionError("Native catalog-denial proof host is unsupported")
