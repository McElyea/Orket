from __future__ import annotations

import json
import logging
from copy import copy
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Protocol

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.sandbox_event_spool import SandboxEventSpool
from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR, capture_log_event_inputs
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


def _capture_event(record: SandboxLifecycleEventRecord) -> SandboxLifecycleEventRecord:
    if type(record) is not SandboxLifecycleEventRecord:
        raise TypeError(LOG_EVENT_INPUT_ERROR)
    _, values = capture_log_event_inputs(
        "sandbox_lifecycle_event", {name: getattr(record, name) for name in SandboxLifecycleEventRecord.model_fields})
    return SandboxLifecycleEventRecord.model_validate(values)


class SandboxLifecycleEventService:
    """Primary event persistence with owned local spool fallback and replay."""

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

    def _capture(self) -> SandboxLifecycleEventService:
        captured = copy(self)
        captured.spool_path, captured.dead_letter_path, captured.lock_path = capture_file_roots(
            [self.spool_path, self.dead_letter_path, self.lock_path])
        captured.max_replay_attempts = int(self.max_replay_attempts)
        return captured

    def _spool(self) -> SandboxEventSpool:
        return SandboxEventSpool(self.spool_path, self.dead_letter_path, self.lock_path)

    async def emit(self, record: SandboxLifecycleEventRecord) -> str:
        selected = _capture_event(record)
        captured, primary = self._capture(), _capture_event(selected)
        return await run_owned_io(lambda: captured._emit(primary, selected), label="sandbox-event-emit", preserve_failure=True)

    async def _emit(self, primary: SandboxLifecycleEventRecord, fallback: SandboxLifecycleEventRecord) -> str:
        try:
            await self.repository.append_event(primary)
            return "primary"
        except Exception as primary_exc:  # noqa: BLE001 - primary boundary selects fallback publication.
            try:
                await self._spool().append(self._encode_spool_line(fallback, retry_count=0))
                return "fallback"
            except Exception as spool_exc:  # noqa: BLE001 - both sink failures must remain explicit.
                raise SandboxLifecycleError(
                    f"Sandbox lifecycle event sinks failed: primary={primary_exc}; spool={spool_exc}"
                ) from spool_exc

    async def replay_spool(self) -> SpoolReplayResult:
        captured = self._capture()
        return await run_owned_io(captured._replay, label="sandbox-event-replay", preserve_failure=True)

    async def _replay(self) -> SpoolReplayResult:
        spool = self._spool()
        if not await spool.exists():
            return SpoolReplayResult(replayed=0, requeued=0, dead_lettered=0)
        async with spool.hold(skip_busy=True) as acquired:
            if not acquired:
                return SpoolReplayResult(replayed=0, requeued=0, dead_lettered=0, lock_acquired=False)
            return await self._replay_locked(spool)

    async def _replay_locked(self, spool: SandboxEventSpool) -> SpoolReplayResult:
        replayed = 0
        remaining: list[str] = []
        dead_lettered: list[str] = []
        for line in await spool.read_lines():
            record, retry_count = self._decode_spool_line(line)
            primary = _capture_event(record)
            try:
                await self.repository.append_event(primary)
                replayed += 1
            except Exception as exc:  # noqa: BLE001 - repository refusal enters retained retry accounting.
                next_retry_count = retry_count + 1
                diagnostic = partial(
                    self._logger.warning, "sandbox_lifecycle_spool_replay_failed",
                    extra={"sandbox_lifecycle_event_id": record.event_id, "retry_count": next_retry_count,
                           "max_replay_attempts": self.max_replay_attempts, "spool_path": str(self.spool_path)},
                    exc_info=(type(exc), exc, exc.__traceback__),
                )
                await run_owned_thread(diagnostic, label="sandbox-spool-replay-diagnostic")
                encoded = self._encode_spool_line(record, retry_count=next_retry_count)
                if next_retry_count >= self.max_replay_attempts:
                    dead_lettered.append(encoded)
                else:
                    remaining.append(encoded)
        await spool.commit_replay(remaining, dead_lettered)
        return SpoolReplayResult(replayed=replayed, requeued=len(remaining), dead_lettered=len(dead_lettered))

    async def _append_spool(self, record: SandboxLifecycleEventRecord) -> None:
        selected = _capture_event(record)
        captured = self._capture()
        line = self._encode_spool_line(selected, retry_count=0)
        await run_owned_io(lambda: captured._spool().append(line), label="sandbox-spool-append", preserve_failure=True)

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
            {"record": record.model_dump(mode="json"), "retry_count": int(retry_count)},
            ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        )
