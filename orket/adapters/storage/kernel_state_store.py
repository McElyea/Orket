"""Native local state effects; application callers own admission and lifetime."""

import json
import shutil
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = True  # Includes publication and removal; never a decision-node port.


def _absolute(path: Path) -> Path:
    require_sync_context(code="E_KERNEL_STATE_REQUIRES_ASYNC_OWNER")
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("E_KERNEL_STATE_ABSOLUTE_PATH_REQUIRED")
    return path


def read_json(path: Path) -> Any:
    return json.loads(_absolute(path).read_bytes().decode("utf-8"))


def write_bytes(path: Path, payload: bytes) -> None:
    path = _absolute(path)
    if type(payload) is not bytes:
        raise TypeError("E_KERNEL_STATE_IMMUTABLE_BYTES_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def exists(path: Path) -> bool:
    return _absolute(path).exists()


def is_directory(path: Path) -> bool:
    return _absolute(path).is_dir()


def is_file(path: Path) -> bool:
    return _absolute(path).is_file()


def paths(path: Path, pattern: str) -> tuple[Path, ...]:
    return tuple(_absolute(path).rglob(pattern))


def make_directory(path: Path) -> None:
    _absolute(path).mkdir(parents=True, exist_ok=True)


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(_absolute(source), _absolute(destination))


def copy_file(source: Path, destination: Path) -> None:
    shutil.copy2(_absolute(source), _absolute(destination))


def replace(source: Path, destination: Path) -> None:
    _absolute(source).replace(_absolute(destination))


def remove_tree(path: Path) -> None:
    shutil.rmtree(_absolute(path))


def remove_file(path: Path) -> None:
    _absolute(path).unlink()
