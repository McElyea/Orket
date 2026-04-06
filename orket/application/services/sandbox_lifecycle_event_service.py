from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiofiles

from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


class SandboxLifecycleEventService:
    """Primary event persistence with local spool fallback and replay."""

    def __init__(self, *, repository, spool_path: str | Path):
        self.repository = repository
        self.spool_path = Path(spool_path)

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

    async def replay_spool(self) -> int:
        if not await asyncio.to_thread(self.spool_path.exists):
            return 0
        async with aiofiles.open(self.spool_path, encoding="utf-8") as handle:
            lines = [line.strip() for line in await handle.readlines() if line.strip()]
        replayed = 0
        remaining: list[str] = []
        for line in lines:
            data = json.loads(line)
            record = SandboxLifecycleEventRecord.model_validate(data)
            try:
                await self.repository.append_event(record)
                replayed += 1
            except Exception:
                remaining.append(line)
        if remaining:
            await self._rewrite_spool(remaining)
        else:
            await asyncio.to_thread(self.spool_path.unlink, missing_ok=True)
        return replayed

    async def _append_spool(self, record: SandboxLifecycleEventRecord) -> None:
        await asyncio.to_thread(self.spool_path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(self.spool_path, "a", encoding="utf-8") as handle:
            await handle.write(record.model_dump_json() + "\n")

    async def _rewrite_spool(self, lines: list[str]) -> None:
        await asyncio.to_thread(self.spool_path.parent.mkdir, parents=True, exist_ok=True)
        async with aiofiles.open(self.spool_path, "w", encoding="utf-8") as handle:
            for line in lines:
                await handle.write(line + "\n")
