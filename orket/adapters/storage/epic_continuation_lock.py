"""Retained epic identity over the shared host-local native lock mechanism."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.core.contracts.epic_approval_recovery import EpicContinuationLockRef
from orket.core.contracts.local_file_lock import LocalFileLockError


class EpicContinuationLocks:
    side_effecting = True

    def __init__(self, journal_path: Path):
        self.journal_path = journal_path
        self._locks = NativeFileLocks(journal_path, suffix=".continuations",
            error_prefix="E_EPIC_APPROVAL_CONTINUATION", empty_key_error="E_EPIC_APPROVAL_CONTINUATION_SESSION_REQUIRED")

    @asynccontextmanager
    async def hold(self, session_id: str, *, expected: EpicContinuationLockRef | None = None):
        async with self._locks.hold(session_id) as observed:
            reference = EpicContinuationLockRef(session_id=session_id, journal_path=observed.root_path,
                lock_path=observed.lock_path, device=observed.device, inode=observed.inode)
            if expected is not None and reference != expected:
                raise LocalFileLockError("E_EPIC_APPROVAL_CONTINUATION_LOCK_CHANGED")
            yield reference
