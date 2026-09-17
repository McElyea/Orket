"""Git-visible file inventory for standalone repository tooling and its tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitInventoryError(RuntimeError):
    """The requested repository inventory could not be established."""


def git_list_files(root: Path) -> list[Path]:
    """Return existing tracked/nonignored untracked files; never fall back to a walk."""
    root = root.resolve(strict=True)
    process = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True, check=False,
    )
    if process.returncode:
        raise GitInventoryError(process.stderr.decode("utf-8", errors="replace").strip())
    files = set()
    for name in process.stdout.split(b"\0"):
        if not name:
            continue
        candidate = root / os.fsdecode(name)
        if not candidate.resolve().is_relative_to(root):
            raise GitInventoryError(f"Git-visible path resolves outside the repository: {candidate.name}")
        if candidate.is_file():
            files.add(candidate)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())
