from __future__ import annotations

import inspect
from typing import Any, Awaitable, Callable, Optional, Protocol

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
        summary: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> Any: ...

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: Optional[str] = None,
        failure_reason: Optional[str] = None,
        summary: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
        finalized_at: Optional[str] = None,
    ) -> Any: ...

    async def get_run(self, session_id: str) -> dict[str, Any] | None: ...


class _ProtocolLedgerRepository(_RunLedgerRepository, Protocol):
    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]: ...

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def list_events(self, session_id: str) -> list[dict[str, Any]]: ...


TelemetrySink = Callable[[dict[str, Any]], Awaitable[None] | None]


class AsyncProtocolPrimaryRunLedgerRepository:
    """
    Compatibility adapter that treats the protocol ledger as the primary event source
    while mirroring run lifecycle state into SQLite and emitting parity telemetry.
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

    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.sqlite_repo.start_run(
            session_id=session_id,
            run_type=run_type,
            run_name=run_name,
            department=department,
            build_id=build_id,
            summary=summary,
            artifacts=artifacts,
        )

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
        failure_class: Optional[str] = None,
        failure_reason: Optional[str] = None,
        summary: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
        finalized_at: Optional[str] = None,
    ) -> None:
        finalize_kwargs = {
            "session_id": session_id,
            "status": status,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary": summary,
            "artifacts": artifacts,
        }
        if finalized_at is not None:
            finalize_kwargs["finalized_at"] = finalized_at
        await self.sqlite_repo.finalize_run(
            **finalize_kwargs,
        )

        protocol_error = await self._try_protocol_write(
            phase="finalize_run",
            session_id=session_id,
            fn=self.protocol_repo.finalize_run(
                **finalize_kwargs,
            ),
        )
        await self._emit_parity(
            phase="finalize_run",
            session_id=session_id,
            protocol_error=protocol_error,
        )

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        if self.primary_mode == "protocol":
            return await self.protocol_repo.get_run(session_id)
        return await self.sqlite_repo.get_run(session_id)

    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
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
        return await self.protocol_repo.append_receipt(
            session_id=session_id,
            receipt=receipt,
        )

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return await self.protocol_repo.list_events(session_id)

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
        except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as exc:
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
                }
            )
            return
        parity_error: str | None = None
        parity_ok = False
        differences: list[dict[str, Any]] = []
        sqlite_digest: str | None = None
        protocol_digest: str | None = None
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
            try:
                log_event(
                    "telemetry_sink_error",
                    {
                        "component": "run_ledger_dual_write",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                    role="system",
                )
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError):
                pass
            return
