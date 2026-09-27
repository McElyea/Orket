"""Spool file effects using the existing host-native owner and owned workers."""
from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from pathlib import Path

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.core.contracts.local_file_lock import LocalFileLockError
from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError

side_effecting = True
_PREFIX = "E_SANDBOX_EVENT_SPOOL"


class SandboxEventSpool:
    """An invocation's selected paths; enclosing service owns the whole admission."""

    def __init__(self, path: Path, dead_letter_path: Path, legacy_lock_path: Path):
        self.path, self.dead_letter_path, self.legacy_lock_path = path, dead_letter_path, legacy_lock_path
        self._locks = NativeFileLocks(path, suffix=".owners", error_prefix=_PREFIX,
                                     empty_key_error=_PREFIX + "_KEY_REQUIRED")

    async def exists(self) -> bool:
        await run_owned_thread(self._refuse_legacy_owner, label="sandbox-spool-legacy-owner")
        return await run_owned_thread(self.path.exists, label="sandbox-spool-exists")

    @asynccontextmanager
    async def hold(self, *, skip_busy: bool = False):
        await run_owned_thread(self._refuse_legacy_owner, label="sandbox-spool-legacy-owner")
        async with AsyncExitStack() as stack:
            try:
                await stack.enter_async_context(self._locks.hold("events"))
            except LocalFileLockError as exc:
                if not skip_busy or str(exc) != _PREFIX + "_UNCERTAIN:owner_busy":
                    raise
                yield False
                return
            await run_owned_thread(self._refuse_legacy_owner, label="sandbox-spool-legacy-owner")
            yield True

    async def append(self, line: str) -> None:
        async with self.hold():
            await run_owned_thread(partial(self._append, self.path, [line]), label="sandbox-spool-append")

    async def read_lines(self) -> list[str]:
        return await run_owned_thread(self._read, label="sandbox-spool-read")

    async def commit_replay(self, remaining: list[str], dead_lettered: list[str]) -> None:
        await run_owned_thread(partial(self._commit, remaining, dead_lettered), label="sandbox-spool-commit")

    def _refuse_legacy_owner(self) -> None:
        try:
            self.legacy_lock_path.lstat()
        except FileNotFoundError:
            return
        raise SandboxLifecycleError(_PREFIX + "_LEGACY_OWNER_UNCERTAIN")

    @staticmethod
    def _append(path: Path, lines: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            for line in lines:
                stream.write(line + "\n")

    def _read(self) -> list[str]:
        try:
            stream = self.path.open(encoding="utf-8")
        except FileNotFoundError:
            return []
        with stream:
            return [line.strip() for line in stream.readlines() if line.strip()]

    def _commit(self, remaining: list[str], dead_lettered: list[str]) -> None:
        if dead_lettered:
            self._append(self.dead_letter_path, dead_lettered)
        if remaining:
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.unlink(missing_ok=True)
            with temporary.open("w", encoding="utf-8") as stream:
                for line in remaining:
                    stream.write(line + "\n")
            temporary.replace(self.path)
        else:
            self.path.unlink(missing_ok=True)
