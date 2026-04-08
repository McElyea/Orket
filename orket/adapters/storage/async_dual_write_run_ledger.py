from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

import aiofiles

from orket.logging import log_event
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class _RunLedgerRepository(Protocol):
    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> Any: ...

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: str | None = None,
        failure_reason: str | None = None,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        finalized_at: str | None = None,
    ) -> Any: ...

    async def get_run(self, session_id: str) -> dict[str, Any] | None: ...


class _ProtocolLedgerRepository(_RunLedgerRepository, Protocol):
    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def list_events(self, session_id: str) -> list[dict[str, Any]]: ...


TelemetrySink = Callable[[dict[str, Any]], Awaitable[None] | None]


class AsyncDualModeLedgerRepository:
    """
    Dual-mode run ledger adapter that mirrors lifecycle state into SQLite and the
    protocol ledger while emitting parity telemetry. `primary_mode` defaults to
    `"sqlite"` so SQLite remains the authoritative read surface unless explicitly
    overridden.
    """

    def __init__(
        self,
        *,
        sqlite_repo: _RunLedgerRepository,
        protocol_repo: _ProtocolLedgerRepository,
        telemetry_sink: TelemetrySink | None = None,
        primary_mode: str = "sqlite",
    ) -> None:
        self.sqlite_repo = sqlite_repo
        self.protocol_repo = protocol_repo
        self.telemetry_sink = telemetry_sink
        normalized_primary = str(primary_mode or "sqlite").strip().lower()
        self.primary_mode = "protocol" if normalized_primary == "protocol" else "sqlite"
        self.sink_failure_count = 0
        self._intent_path = self._resolve_intent_path()
        self._intent_lock = asyncio.Lock()
        self._recovery_lock = asyncio.Lock()
        self._recovery_complete = False
        self._recovery_run_once = False

    async def initialize(self) -> None:
        if self._recovery_run_once:
            return
        async with self._recovery_lock:
            if self._recovery_run_once:
                return
            intents = await self._load_intents()
            if not intents:
                self._recovery_complete = True
                self._recovery_run_once = True
                return
            unresolved: list[dict[str, Any]] = []
            for intent in intents:
                recovered = await self._recover_intent(dict(intent))
                if recovered is not None:
                    unresolved.append(recovered)
            await self._write_intents(unresolved)
            self._recovery_complete = not unresolved
            self._recovery_run_once = True

    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        await self.initialize()
        intent_id = await self._record_intent(
            operation="start_run",
            session_id=session_id,
            kwargs={
                "session_id": session_id,
                "run_type": run_type,
                "run_name": run_name,
                "department": department,
                "build_id": build_id,
                "summary": dict(summary or {}),
                "artifacts": dict(artifacts or {}),
            },
        )
        await self.sqlite_repo.start_run(
            session_id=session_id,
            run_type=run_type,
            run_name=run_name,
            department=department,
            build_id=build_id,
            summary=summary,
            artifacts=artifacts,
        )
        await self._update_intent(intent_id, sqlite_ack=True)

        protocol_error = await self._try_protocol_write(
            phase="start_run",
            session_id=session_id,
            fn=self.protocol_repo.start_run(
                session_id=session_id,
                run_type=run_type,
                run_name=run_name,
                department=department,
                build_id=build_id,
                summary=summary,
                artifacts=artifacts,
            ),
        )
        if protocol_error is None:
            await self._update_intent(intent_id, protocol_ack=True, protocol_error=None)
            await self._clear_intent(intent_id)
        else:
            await self._update_intent(intent_id, protocol_error=protocol_error)
        await self._emit_parity(
            phase="start_run",
            session_id=session_id,
            protocol_error=protocol_error,
        )

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: str | None = None,
        failure_reason: str | None = None,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
        finalized_at: str | None = None,
    ) -> None:
        await self.initialize()
        finalize_intent_kwargs: dict[str, Any] = {
            "session_id": session_id,
            "status": status,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary": summary,
            "artifacts": artifacts,
        }
        if finalized_at is not None:
            finalize_intent_kwargs["finalized_at"] = finalized_at
        intent_id = await self._record_intent(
            operation="finalize_run",
            session_id=session_id,
            kwargs=dict(finalize_intent_kwargs),
        )
        if finalized_at is None:
            await self.sqlite_repo.finalize_run(
                session_id=session_id,
                status=status,
                failure_class=failure_class,
                failure_reason=failure_reason,
                summary=summary,
                artifacts=artifacts,
            )
        else:
            await self.sqlite_repo.finalize_run(
                session_id=session_id,
                status=status,
                failure_class=failure_class,
                failure_reason=failure_reason,
                summary=summary,
                artifacts=artifacts,
                finalized_at=finalized_at,
            )
        await self._update_intent(intent_id, sqlite_ack=True)

        if finalized_at is None:
            protocol_finalize = self.protocol_repo.finalize_run(
                session_id=session_id,
                status=status,
                failure_class=failure_class,
                failure_reason=failure_reason,
                summary=summary,
                artifacts=artifacts,
            )
        else:
            protocol_finalize = self.protocol_repo.finalize_run(
                session_id=session_id,
                status=status,
                failure_class=failure_class,
                failure_reason=failure_reason,
                summary=summary,
                artifacts=artifacts,
                finalized_at=finalized_at,
            )
        protocol_error = await self._try_protocol_write(
            phase="finalize_run",
            session_id=session_id,
            fn=protocol_finalize,
        )
        if protocol_error is None:
            await self._update_intent(intent_id, protocol_ack=True, protocol_error=None)
            await self._clear_intent(intent_id)
        else:
            await self._update_intent(intent_id, protocol_error=protocol_error)
        await self._emit_parity(
            phase="finalize_run",
            session_id=session_id,
            protocol_error=protocol_error,
        )

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        await self.initialize()
        if self.primary_mode == "protocol":
            return await self.protocol_repo.get_run(session_id)
        return await self.sqlite_repo.get_run(session_id)

    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self.initialize()
        return await self.protocol_repo.append_event(
            session_id=session_id,
            kind=kind,
            payload=payload,
        )

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        await self.initialize()
        return await self.protocol_repo.append_receipt(
            session_id=session_id,
            receipt=receipt,
        )

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        await self.initialize()
        return await self.protocol_repo.list_events(session_id)

    def _resolve_intent_path(self) -> Path:
        sqlite_db_path = getattr(self.sqlite_repo, "db_path", None)
        if sqlite_db_path is not None:
            return Path(str(sqlite_db_path)).resolve().parent / ".orket" / "dual_write_intents.json"
        protocol_root = getattr(self.protocol_repo, "root", None)
        if protocol_root is not None:
            return Path(protocol_root) / ".orket" / "dual_write_intents.json"
        return Path.cwd() / ".orket" / "dual_write_intents.json"

    async def _recover_pending_intents(self) -> None:
        await self.initialize()

    async def _recover_intent(self, intent: dict[str, Any]) -> dict[str, Any] | None:
        operation = str(intent.get("operation") or "").strip()
        session_id = str(intent.get("session_id") or "").strip()
        kwargs = dict(intent.get("kwargs") or {})

        sqlite_ack = bool(intent.get("sqlite_ack")) or await self._backend_acknowledged(
            repo=self.sqlite_repo,
            operation=operation,
            session_id=session_id,
            kwargs=kwargs,
        )
        protocol_ack = bool(intent.get("protocol_ack")) or await self._backend_acknowledged(
            repo=self.protocol_repo,
            operation=operation,
            session_id=session_id,
            kwargs=kwargs,
        )
        intent["sqlite_ack"] = sqlite_ack
        intent["protocol_ack"] = protocol_ack

        if not sqlite_ack:
            sqlite_error = await self._try_replay_intent_write(
                repo=self.sqlite_repo,
                operation=operation,
                session_id=session_id,
                kwargs=kwargs,
            )
            if sqlite_error is not None:
                intent["sqlite_error"] = sqlite_error
                return intent
            intent["sqlite_ack"] = True
            intent["sqlite_error"] = None

        if not protocol_ack:
            protocol_error = await self._try_replay_intent_write(
                repo=self.protocol_repo,
                operation=operation,
                session_id=session_id,
                kwargs=kwargs,
            )
            if protocol_error is not None:
                intent["protocol_error"] = protocol_error
                return intent
            intent["protocol_ack"] = True
            intent["protocol_error"] = None

        return None

    async def _backend_acknowledged(
        self,
        *,
        repo: _RunLedgerRepository,
        operation: str,
        session_id: str,
        kwargs: dict[str, Any],
    ) -> bool:
        try:
            if operation == "start_run":
                run = await repo.get_run(session_id)
                return run is not None
            if operation == "finalize_run":
                run = await repo.get_run(session_id)
                if run is None:
                    return False
                return (
                    str(run.get("status") or "") == str(kwargs.get("status") or "")
                    and str(run.get("failure_class") or "") == str(kwargs.get("failure_class") or "")
                    and str(run.get("failure_reason") or "") == str(kwargs.get("failure_reason") or "")
                )
        except (RuntimeError, ValueError, OSError):
            return False
        return False

    async def _try_replay_intent_write(
        self,
        *,
        repo: _RunLedgerRepository,
        operation: str,
        session_id: str,
        kwargs: dict[str, Any],
    ) -> str | None:
        if operation == "start_run":
            return await self._try_protocol_write(
                phase="intent_recovery_start_run",
                session_id=session_id,
                fn=repo.start_run(**kwargs),
            )
        if operation == "finalize_run":
            return await self._try_protocol_write(
                phase="intent_recovery_finalize_run",
                session_id=session_id,
                fn=repo.finalize_run(**kwargs),
            )
        return f"RuntimeError:unsupported dual-write recovery operation '{operation}'"

    async def _record_intent(
        self,
        *,
        operation: str,
        session_id: str,
        kwargs: dict[str, Any],
    ) -> str:
        intent_id = f"{operation}:{session_id}"
        intent = {
            "intent_id": intent_id,
            "operation": str(operation),
            "session_id": str(session_id),
            "kwargs": dict(kwargs),
            "sqlite_ack": False,
            "protocol_ack": False,
            "sqlite_error": None,
            "protocol_error": None,
        }
        async with self._intent_lock:
            intents = await self._load_intents()
            intents = [row for row in intents if str(row.get("intent_id") or "") != intent_id]
            intents.append(intent)
            await self._write_intents(intents)
        self._recovery_complete = False
        return intent_id

    async def _update_intent(self, intent_id: str, **updates: Any) -> None:
        async with self._intent_lock:
            intents = await self._load_intents()
            updated: list[dict[str, Any]] = []
            for row in intents:
                if str(row.get("intent_id") or "") == intent_id:
                    current = dict(row)
                    current.update(dict(updates))
                    updated.append(current)
                    continue
                updated.append(dict(row))
            await self._write_intents(updated)
        self._recovery_complete = False

    async def _clear_intent(self, intent_id: str) -> None:
        async with self._intent_lock:
            intents = await self._load_intents()
            pending = [row for row in intents if str(row.get("intent_id") or "") != intent_id]
            await self._write_intents(pending)
        self._recovery_complete = False

    async def _load_intents(self) -> list[dict[str, Any]]:
        if not await asyncio.to_thread(self._intent_path.exists):
            return []
        async with aiofiles.open(self._intent_path, "r", encoding="utf-8") as handle:
            raw = await handle.read()
        if not str(raw).strip():
            return []
        payload = json.loads(raw)
        rows = payload.get("pending")
        if not isinstance(rows, list):
            raise RuntimeError(f"E_DUAL_WRITE_INTENT_SCHEMA:{self._intent_path}")
        return [dict(row) for row in rows if isinstance(row, dict)]

    async def _write_intents(self, intents: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(self._intent_path.parent.mkdir, parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "pending": [dict(row) for row in intents],
        }
        async with aiofiles.open(self._intent_path, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n")

    async def _try_protocol_write(
        self,
        *,
        phase: str,
        session_id: str,
        fn: Any,
    ) -> str | None:
        try:
            if inspect.isawaitable(fn):
                await fn
            return None
        except (RuntimeError, ValueError, OSError) as exc:
            await self._emit(
                {
                    "kind": "run_ledger_dual_write_error",
                    "phase": str(phase),
                    "session_id": str(session_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
            return f"{type(exc).__name__}:{exc}"

    async def _emit_parity(
        self,
        *,
        phase: str,
        session_id: str,
        protocol_error: str | None,
    ) -> None:
        if protocol_error is not None:
            await self._emit(
                {
                    "kind": "run_ledger_dual_write_parity",
                    "phase": str(phase),
                    "session_id": str(session_id),
                    "parity_ok": False,
                    "parity_skip_reason": "protocol_write_failed",
                    "difference_count": 0,
                    "differences": [],
                    "sqlite_digest": None,
                    "protocol_digest": None,
                    "protocol_error": protocol_error,
                    "parity_error": None,
                    "parity_check_error": False,
                }
            )
            return
        parity_error: str | None = None
        parity_ok = False
        differences: list[dict[str, Any]] = []
        sqlite_digest: str | None = None
        protocol_digest: str | None = None
        parity_check_error = False
        try:
            parity = await compare_run_ledger_rows(
                sqlite_repo=self.sqlite_repo,
                protocol_repo=self.protocol_repo,
                session_id=session_id,
            )
            parity_ok = bool(parity.get("parity_ok", False))
            differences = list(parity.get("differences") or [])
            sqlite_digest = parity.get("sqlite_digest")
            protocol_digest = parity.get("protocol_digest")
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            parity_error = f"{type(exc).__name__}:{exc}"
            parity_check_error = True

        await self._emit(
            {
                "kind": "run_ledger_dual_write_parity",
                "phase": str(phase),
                "session_id": str(session_id),
                "parity_ok": parity_ok,
                "difference_count": len(differences),
                "differences": differences,
                "sqlite_digest": sqlite_digest,
                "protocol_digest": protocol_digest,
                "protocol_error": protocol_error,
                "parity_error": parity_error,
                "parity_check_error": parity_check_error,
            }
        )

    async def _emit(self, payload: dict[str, Any]) -> None:
        sink = self.telemetry_sink
        if sink is None:
            return
        try:
            outcome = sink(payload)
            if inspect.isawaitable(outcome):
                await outcome
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
            self.sink_failure_count += 1
            # Telemetry sink failure must stay non-fatal but observable.
            with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError, AttributeError):
                log_event(
                    "telemetry_sink_error",
                    {
                        "component": "run_ledger_dual_write",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    role="system",
                )
            return
