from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import aiofiles

from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


class _SandboxLifecycleEventRepository(Protocol):
    async def append_event(self, record: SandboxLifecycleEventRecord) -> Any: ...


@dataclass(frozen=True)
class SpoolReplayResult:
    replayed: int
    requeued: int
    dead_lettered: int
    lock_acquired: bool = True


class SandboxLifecycleEventService:
    """Primary event persistence with local spool fallback and replay."""

    def __init__(
        self, *, repository: _SandboxLifecycleEventRepository, spool_path: str | Path, max_replay_attempts: int = 3
    ) -> None:
        if max_replay_attempts < 1:
            raise ValueError("max_replay_attempts must be at least 1")
        self.repository = repository
        self.spool_path = Path(spool_path)
        self.dead_letter_path = self.spool_path.with_suffix(self.spool_path.suffix + ".deadletter")
        self.lock_path = self.spool_path.with_suffix(self.spool_path.suffix + ".lock")
        self.max_replay_attempts = int(max_replay_attempts)
        self._logger = logging.getLogger(__name__)

    async def emit(self, record: SandboxLifecycleEventRecord) -> str:
        try:
            await self.repository.append_event(record)
            return "primary"
        except Exception as primary_exc:
            try:
                await self._append_spool(record)
                return "fallback"
            except Exception as spool_exc:
                raise SandboxLifecycleError(
                    f"Sandbox lifecycle event sinks failed: primary={primary_exc}; spool={spool_exc}"
                ) from spool_exc

    async def replay_spool(self) -> SpoolReplayResult:
        if not await asyncio.to_thread(self.spool_path.exists):
            return SpoolReplayResult(replayed=0, requeued=0, dead_lettered=0)

        lock_fd = await self._try_acquire_replay_lock()
        if lock_fd is None:
            return SpoolReplayResult(replayed=0, requeued=0, dead_lettered=0, lock_acquired=False)

        try:
            async with aiofiles.open(self.spool_path, encoding="utf-8") as handle:
                lines = [line.strip() for line in await handle.readlines() if line.strip()]
            replayed = 0
            remaining: list[str] = []
            dead_lettered: list[str] = []
            for line in lines:
                record, retry_count = self._decode_spool_line(line)
                try:
                    await self.repository.append_event(record)
                    replayed += 1
                except Exception as exc:  # noqa: BLE001 - repository boundary must fail into spool retry accounting.
                    next_retry_count = retry_count + 1
                    self._logger.warning(
                        "sandbox_lifecycle_spool_replay_failed",
                        extra={
                            "sandbox_lifecycle_event_id": record.event_id,
                            "retry_count": next_retry_count,
                            "max_replay_attempts": self.max_replay_attempts,
                            "spool_path": str(self.spool_path),
                        },
                        exc_info=exc,
                    )
                    encoded = self._encode_spool_line(record, retry_count=next_retry_count)
                    if next_retry_count >= self.max_replay_attempts:
                        dead_lettered.append(encoded)
                    else:
                        remaining.append(encoded)
            if dead_lettered:
                await self._append_dead_letter(dead_lettered)
            if remaining:
                await self._rewrite_spool(remaining)
            else:
                await asyncio.to_thread(self.spool_path.unlink, missing_ok=True)
            return SpoolReplayResult(replayed=replayed, requeued=len(remaining), dead_lettered=len(dead_lettered))
        finally:
            await self._release_replay_lock(lock_fd)

    async def _append_spool(self, record: SandboxLifecycleEventRecord) -> None:
        await asyncio.to_thread(self.spool_path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(self.spool_path, "a", encoding="utf-8") as handle:
            await handle.write(self._encode_spool_line(record, retry_count=0) + "\n")

    async def _rewrite_spool(self, lines: list[str]) -> None:
        await asyncio.to_thread(self.spool_path.parent.mkdir, parents=True, exist_ok=True)
        tmp_path = self.spool_path.with_suffix(self.spool_path.suffix + ".tmp")
        await asyncio.to_thread(tmp_path.unlink, missing_ok=True)
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as handle:
            for line in lines:
                await handle.write(line + "\n")
        await asyncio.to_thread(os.replace, tmp_path, self.spool_path)

    async def _append_dead_letter(self, lines: list[str]) -> None:
        await asyncio.to_thread(self.dead_letter_path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(self.dead_letter_path, "a", encoding="utf-8") as handle:
            for line in lines:
                await handle.write(line + "\n")

    def _decode_spool_line(self, line: str) -> tuple[SandboxLifecycleEventRecord, int]:
        data = json.loads(line)
        retry_count = 0
        record_data = data
        if isinstance(data, dict) and isinstance(data.get("record"), dict):
            record_data = data["record"]
            retry_count = int(data.get("retry_count") or 0)
        return SandboxLifecycleEventRecord.model_validate(record_data), retry_count

    def _encode_spool_line(self, record: SandboxLifecycleEventRecord, *, retry_count: int) -> str:
        return json.dumps(
            {
                "record": record.model_dump(mode="json"),
                "retry_count": int(retry_count),
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    async def _try_acquire_replay_lock(self) -> int | None:
        await asyncio.to_thread(self.lock_path.parent.mkdir, parents=True, exist_ok=True)

        def _open_exclusive() -> int | None:
            try:
                return os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
            except FileExistsError:
                return None

        return await asyncio.to_thread(_open_exclusive)

    async def _release_replay_lock(self, lock_fd: int) -> None:
        def _release() -> None:
            os.close(lock_fd)
            try:
                os.unlink(self.lock_path)
            except FileNotFoundError:
                return

        await asyncio.to_thread(_release)
