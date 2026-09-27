"""Native names for the same retained Windows Git repository, without relocation."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = True


def needs_native_repository_paths(repo_dir: Path) -> bool:
    # Git bootstrap/config locking can run before core.longpaths is effective.
    return os.name == "nt" and len(str(repo_dir / ".git/config.lock").encode("utf-16-le")) // 2 >= 260


def _short_path(path: Path) -> Path:
    function = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
    function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    function.restype = ctypes.c_uint
    size = function(str(path), None, 0)
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(size)
    written = function(str(path), buffer, size)
    if not written or written >= size:
        raise RuntimeError("E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE")
    return Path(buffer.value)


def native_repository_arguments(repo_dir: Path, *, initialize: bool) -> tuple[tuple[str, ...], str]:
    require_sync_context(code="E_GITEA_GIT_PATH_REQUIRES_ASYNC_OWNER")
    git_dir = repo_dir / ".git"
    try:
        if initialize:
            # This is the original object store, not another cache or a filesystem alias.
            git_dir.mkdir(exist_ok=True)
        worktree, common = _short_path(repo_dir), _short_path(git_dir)
        # Git for Windows checks explicit GIT_DIR against PATH_MAX minus 40 bytes.
        # GetShortPathNameW may return an unchanged, unusably long path.
        if (not worktree.is_absolute() or not common.is_absolute()
                or len(str(common).encode("utf-8")) > 220
                or len(str(worktree).encode("utf-16-le")) // 2 >= 260
                or not worktree.is_dir() or not common.is_dir()
                or not worktree.samefile(repo_dir) or not common.samefile(git_dir)):
            raise RuntimeError("E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("E_GITEA_GIT_NATIVE_PATH_UNAVAILABLE") from exc
    return (f"--git-dir={common}", f"--work-tree={worktree}"), str(common)
