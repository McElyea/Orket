"""Application authority for bound, verified dual-backend lifecycle recovery."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.dual_write_intent_store import DualWriteIntentStore
from orket.adapters.storage.protocol_ledger_io import owned_protocol_io
from orket.application.services.dual_write_telemetry import DualWriteTelemetry
from orket.core.contracts.dual_write_intent import (
    DualWriteLedgerError,
    intent_matches_row,
    require_replayable,
    validate_intent,
)
from orket.core.contracts.result_error_invariants import validate_result_error_invariant

TelemetrySink = Callable[[dict[str, Any]], Awaitable[None] | None]


class AsyncDualModeLedgerRepository:
    """SQLite primary permits explicit degraded mirroring; protocol primary refuses it."""

    def __init__(self, *, sqlite_repo, protocol_repo, telemetry_sink: TelemetrySink | None = None,
                 primary_mode: str = "sqlite", protocol_root=None):
        root = protocol_root if protocol_root is not None else getattr(protocol_repo, "root", None)
        if root is None or getattr(sqlite_repo, "db_path", None) is None:
            raise DualWriteLedgerError("BINDING_REQUIRED:sqlite_path_and_protocol_root")
        self.sqlite_repo, self.protocol_repo = sqlite_repo, protocol_repo
        self.primary_mode = str(primary_mode or "sqlite").strip().lower()
        if self.primary_mode not in ("sqlite", "protocol"):
            raise DualWriteLedgerError("PRIMARY_MODE_INVALID")
        self._store = DualWriteIntentStore(sqlite_path=sqlite_repo.db_path, protocol_root=root)
        self._intent_path = self._store.path
        self._lock = asyncio.Lock()
        self._telemetry = DualWriteTelemetry(telemetry_sink)

    @property
    def sink_failure_count(self):
        return self._telemetry.failure_count

    async def _owned(self, operation):
        async with self._lock, self._store.hold():
            self._intent_path = self._store.path
            await owned_protocol_io(self._check_binding)
            return await run_owned_io(operation, label="dual-ledger-lifecycle", preserve_failure=True)

    def _check_binding(self):
        actual_root = getattr(self.protocol_repo, "root", self._store.protocol_root)
        if (Path(self.sqlite_repo.db_path).resolve() != self._store.sqlite_path
                or Path(actual_root).resolve() != self._store.protocol_root):
            raise DualWriteLedgerError("BINDING_DRIFT")

    async def initialize(self):
        await self._owned(self._recover)

    async def _load_intents(self):
        async with self._lock, self._store.hold():
            return await self._store.load()

    async def _recover(self):
        intents = await self._store.load()
        for intent in list(intents):
            error = await self._apply(intent, intents)
            if error is not None and self.primary_mode == "protocol":
                raise DualWriteLedgerError(f"PRIMARY_UNAVAILABLE:{error}")
        return intents

    async def start_run(self, *, session_id, run_type, run_name, department, build_id, summary=None, artifacts=None):
        kwargs = deepcopy(dict(session_id=session_id, run_type=run_type, run_name=run_name,
                               department=department, build_id=build_id, summary=summary or {}, artifacts=artifacts or {}))
        await self._lifecycle("start_run", kwargs)

    async def finalize_run(self, *, session_id, status, failure_class=None, failure_reason=None,
                           summary=None, artifacts=None, finalized_at=None):
        status = validate_result_error_invariant(status=status, failure_class=failure_class, failure_reason=failure_reason)
        kwargs = deepcopy(dict(session_id=session_id, status=status, failure_class=failure_class,
                               failure_reason=failure_reason, summary=summary, artifacts=artifacts))
        if finalized_at is not None:
            kwargs["finalized_at"] = finalized_at
        await self._lifecycle("finalize_run", kwargs)

    async def _lifecycle(self, operation, kwargs):
        intent = dict(intent_id=f"{operation}:{kwargs['session_id']}", operation=operation,
                      session_id=kwargs["session_id"], kwargs=kwargs, sqlite_ack=False, protocol_ack=False,
                      sqlite_error=None, protocol_error=None)
        validate_intent(intent)

        async def execute():
            intents = await self._recover()
            if any(row["session_id"] == intent["session_id"] for row in intents):
                raise DualWriteLedgerError(f"PENDING:{intent['intent_id']}")
            # Verify both existing states before either backend can replace a conflicting start.
            for backend in (self.sqlite_repo, self.protocol_repo):
                require_replayable(intent, await self._observe(backend, intent))
            intents.append(intent)
            await self._store.write(intents)
            error = await self._apply(intent, intents)
            await self._telemetry.parity(sqlite_repo=self.sqlite_repo, protocol_repo=self.protocol_repo,
                                         phase=operation, session_id=intent["session_id"], protocol_error=error)
            if error is not None and self.primary_mode == "protocol":
                raise DualWriteLedgerError(f"PRIMARY_UNAVAILABLE:{error}")

        await self._owned(execute)

    async def _apply(self, intent, intents):
        # Flags record observations, but every attempt revalidates actual backend content.
        for backend in (self.sqlite_repo, self.protocol_repo):
            require_replayable(intent, await self._observe(backend, intent))
        for name, backend in (("sqlite", self.sqlite_repo), ("protocol", self.protocol_repo)):
            try:
                row = await self._observe(backend, intent)
                require_replayable(intent, row)
                if not intent_matches_row(intent, row):
                    operation = backend.start_run if intent["operation"] == "start_run" else backend.finalize_run
                    await operation(**deepcopy(intent["kwargs"]))
                    row = await self._observe(backend, intent)
                    if not intent_matches_row(intent, row):
                        raise DualWriteLedgerError(f"EFFECT_UNVERIFIED:{name}:{intent['intent_id']}")
            except DualWriteLedgerError:
                raise
            except (RuntimeError, ValueError, OSError) as exc:
                intent[name + "_error"] = f"{type(exc).__name__}:{exc}"
                intent[name + "_ack"] = False
                await self._store.write(intents)
                await self._telemetry.emit({"kind": "run_ledger_dual_write_error", "phase": intent["operation"],
                                            "session_id": intent["session_id"], "backend": name,
                                            "error_type": type(exc).__name__, "error": str(exc)})
                if name == "sqlite":
                    raise
                return intent[name + "_error"]
            intent[name + "_ack"], intent[name + "_error"] = True, None
            await self._store.write(intents)
        intents.remove(intent)
        await self._store.write(intents)
        return None

    async def _observe(self, backend, intent):
        row = await backend.get_run(intent["session_id"])
        if row is not None and backend is self.protocol_repo and intent["kwargs"].get("finalized_at") is not None:
            events = await backend.list_events(intent["session_id"])
            finals = [event for event in events if event.get("kind") == "run_finalized"]
            row = dict(row, ended_at=finals[-1].get("timestamp") if finals else None)
        return row

    async def get_run(self, session_id):
        async def read():
            await self._recover()
            repo = self.protocol_repo if self.primary_mode == "protocol" else self.sqlite_repo
            return await repo.get_run(session_id)
        return await self._owned(read)

    async def append_event(self, *, session_id, kind, payload=None):
        captured = deepcopy(payload)

        async def append():
            await self._recover()
            return await self.protocol_repo.append_event(session_id=session_id, kind=kind, payload=captured)
        return await self._owned(append)

    async def append_receipt(self, *, session_id, receipt):
        captured = deepcopy(receipt)

        async def append():
            await self._recover()
            return await self.protocol_repo.append_receipt(session_id=session_id, receipt=captured)
        return await self._owned(append)

    async def list_events(self, session_id):
        async def read():
            await self._recover()
            return await self.protocol_repo.list_events(session_id)
        return await self._owned(read)
