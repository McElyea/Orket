"""Verified rotating diagnostics with retained native file ownership."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.file_admission import require_regular_or_absent
from orket.adapters.storage.local_file_lock import NativeFileLocks

side_effecting = True


@dataclass(frozen=True)
class CrashLogStore:
    side_effecting = True
    workspace: Path
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 5

    def __post_init__(self) -> None:
        if not self.workspace.is_absolute():
            raise ValueError("E_CRASH_WORKSPACE_ABSOLUTE_REQUIRED")
        if self.max_bytes < 1 or self.backup_count < 1:
            raise ValueError("E_CRASH_ROTATION_LIMIT_INVALID")

    async def append(self, content: str) -> Path:
        payload = content.encode("utf-8")
        if not payload:
            raise ValueError("E_CRASH_RECORD_EMPTY")
        return await run_owned_thread(lambda: self._append_sync(payload), label="crash-log-publication")

    def _append_sync(self, payload: bytes) -> Path:
        root = self.workspace.resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = root / "orket_crash.log"
        require_regular_or_absent(target, error_code="E_CRASH_LOG_NOT_REGULAR")
        locks = NativeFileLocks(target, suffix=".owners", error_prefix="E_CRASH", empty_key_error="E_CRASH_KEY")
        with locks.hold_sync("append"):
            for path in [target, *[target.with_name(f"{target.name}.{n}") for n in range(1, self.backup_count + 1)]]:
                require_regular_or_absent(path, error_code="E_CRASH_LOG_NOT_REGULAR")
            if target.exists() and target.stat().st_size + len(payload) >= self.max_bytes:
                self._rotate(target)
            _append_bytes(target, payload)
            _verify_tail(target, payload)
        return target

    def _rotate(self, target: Path) -> None:
        for number in range(self.backup_count, 0, -1):
            source = target if number == 1 else target.with_name(f"{target.name}.{number - 1}")
            destination = target.with_name(f"{target.name}.{number}")
            if source.exists():
                source.replace(destination)


def _append_bytes(target: Path, payload: bytes) -> None:
    """Only called inside the owned worker and its native append admission."""
    with target.open("ab") as handle:
        if handle.write(payload) != len(payload):
            raise OSError("E_CRASH_LOG_SHORT_WRITE")
        handle.flush()
        os.fsync(handle.fileno())


def _verify_tail(target: Path, payload: bytes) -> None:
    with target.open("rb") as handle:
        handle.seek(-len(payload), os.SEEK_END)
        if handle.read() != payload:
            raise OSError("E_CRASH_LOG_UNVERIFIED")
