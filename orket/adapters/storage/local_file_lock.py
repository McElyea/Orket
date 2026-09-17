"""Shared nonblocking native locks with owned acquisition and release threads."""
from __future__ import annotations

import asyncio
import errno
import hashlib
import os
import stat
from contextlib import asynccontextmanager
from pathlib import Path

from orket.core.contracts.local_file_lock import LocalFileLockError, LocalFileLockRef


class NativeFileLocks:
    side_effecting = True

    def __init__(self, root_path: Path, *, suffix: str, error_prefix: str, empty_key_error: str):
        self.root_path, self.suffix = root_path, suffix
        self.error_prefix, self.empty_key_error = error_prefix, empty_key_error

    @asynccontextmanager
    async def hold(self, key: str):
        operation = asyncio.create_task(asyncio.to_thread(
            _acquire, self.root_path, self.suffix, key, self.error_prefix, self.empty_key_error))
        (descriptor, reference), cancelled = await _settle(operation)
        try:
            if cancelled is not None:
                raise cancelled
            yield reference
        finally:
            _, cancelled = await _settle(asyncio.create_task(asyncio.to_thread(_release, descriptor)))
            if cancelled is not None:
                raise cancelled


async def _settle(operation):
    """Never abandon an acquisition/release thread under repeated cancellation."""
    cancelled = None
    while not operation.done():
        try:
            await asyncio.shield(operation)
        except asyncio.CancelledError as exc:
            cancelled = exc
    return operation.result(), cancelled


def _release(descriptor: int) -> None:
    os.close(descriptor)


def _reject_link(path: Path, prefix: str) -> None:
    try:
        observed = path.lstat()
    except FileNotFoundError:
        return
    if (stat.S_ISLNK(observed.st_mode)
            or getattr(observed, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise LocalFileLockError(prefix + "_LOCK_LINK")


def _acquire(root_path: Path, suffix: str, key: str, prefix: str, empty_key_error: str):
    if not key:
        raise LocalFileLockError(empty_key_error)
    root = root_path.resolve()
    directory = root.with_name(root.name + suffix)
    _reject_link(directory, prefix)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256(key.encode("utf-8")).hexdigest() + ".lock")
    _reject_link(path, prefix)
    if not path.resolve().is_relative_to(directory.resolve()):
        raise LocalFileLockError(prefix + "_LOCK_PATH")
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    acquired = False
    try:
        os.set_inheritable(descriptor, False)
        _lock(descriptor, prefix)
        observed, current = os.fstat(descriptor), path.stat()
        if not stat.S_ISREG(observed.st_mode) or (observed.st_dev, observed.st_ino) != (current.st_dev, current.st_ino):
            raise LocalFileLockError(prefix + "_LOCK_CHANGED")
        reference = LocalFileLockRef(str(root), str(path), observed.st_dev, observed.st_ino)
        acquired = True
        return descriptor, reference
    finally:
        if not acquired:
            os.close(descriptor)


def _lock(descriptor: int, prefix: str) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        elif os.name == "posix":
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            raise RuntimeError(prefix + "_HOST_UNSUPPORTED")
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN):
            raise LocalFileLockError(prefix + "_UNCERTAIN:owner_busy") from exc
        raise
