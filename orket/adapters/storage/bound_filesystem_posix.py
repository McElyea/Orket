"""POSIX descriptor-relative filesystem operations; called only in an owned thread."""

from __future__ import annotations

import os
import stat
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path

side_effecting = True


@contextmanager
def open_target(root: Path, target: Path, requested: Path, *, operation: str):
    if (not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY")
            or not {os.open, os.mkdir, os.unlink}.issubset(os.supports_dir_fd)):
        raise RuntimeError("E_OUTWARD_BOUND_FILESYSTEM_HOST_UNSUPPORTED")
    # O_PATH pins Linux directories without requiring read permission in addition to traversal.
    path_access = getattr(os, "O_PATH", os.O_RDONLY)
    flags = path_access | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as owned:
        directory = os.open(target.anchor, flags)
        owned.callback(os.close, directory)
        current = Path(target.anchor)
        for part in target.parent.parts[1:]:
            current /= part
            if operation in {"write_file", "create_directory"} and current.is_relative_to(root):
                # Existing entries still must pass the no-follow directory open.
                with suppress(FileExistsError):
                    os.mkdir(part, dir_fd=directory)
            directory = os.open(part, flags, dir_fd=directory)
            owned.callback(os.close, directory)
        if root.resolve() != root or requested.resolve() != target:
            raise RuntimeError("E_OUTWARD_AUTHORIZATION_TARGET_DRIFT")
        if operation == "create_directory":
            # Existing entries still must pass the no-follow directory open.
            with suppress(FileExistsError):
                os.mkdir(target.name, dir_fd=directory)
            descriptor = os.open(target.name, flags, dir_fd=directory)
            owned.callback(os.close, descriptor)
        else:
            access = {"write_file": os.O_WRONLY | os.O_CREAT, "read_file": os.O_RDONLY,
                      "delete_file": path_access}[operation]
            descriptor = os.open(target.name, access | os.O_NOFOLLOW | os.O_NONBLOCK, 0o666, dir_fd=directory)
            owned.callback(os.close, descriptor)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise RuntimeError("E_OUTWARD_BOUND_FILESYSTEM_REGULAR_FILE_REQUIRED")
        yield descriptor, lambda: os.unlink(target.name, dir_fd=directory)
