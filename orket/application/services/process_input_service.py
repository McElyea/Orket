"""Capture invocation context without filesystem traversal or a mutable ambient cache."""
from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType


def absolute_process_path(path: str | Path, base: Path) -> Path:
    selected = Path(path)
    if selected.drive and not selected.is_absolute():
        raise ValueError("E_PROCESS_DRIVE_RELATIVE_PATH_UNSUPPORTED")
    return selected if selected.is_absolute() else base / selected


def capture_process_context(
    *, cwd: str | Path | None = None, environment: Mapping[str, str] | None = None,
) -> tuple[Path, Mapping[str, str]]:
    directory = Path.cwd() if cwd is None else Path(cwd)
    if not directory.is_absolute():
        directory = absolute_process_path(directory, Path.cwd())
    return directory, MappingProxyType(dict(os.environ if environment is None else environment))
