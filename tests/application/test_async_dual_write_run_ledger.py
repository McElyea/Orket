from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_dual_write_run_ledger import AsyncDualModeLedgerRepository
from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository


@pytest.mark.asyncio
async def test_async_run_ledger_finalize_rejects_done_with_failure(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    await sqlite_repo.start_run(
        session_id="sess-invariant",
        run_type="epic",
        run_name="Invariant",
        department="core",
        build_id="build-1",
    )
    with pytest.raises(ValueError, match="E_RESULT_ERROR_INVARIANT:done_must_not_have_failure"):
        await sqlite_repo.finalize_run(
            session_id="sess-invariant",
            status="done",
            failure_class="ExecutionFailed",
            failure_reason="should not be set on done",
        )


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_writes_both_backends_and_reports_clean_parity(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    telemetry: list[dict[str, Any]] = []

    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        telemetry_sink=lambda payload: telemetry.append(dict(payload)),
    )
    await dual_repo.start_run(
        session_id="sess-1",
        run_type="epic",
        run_name="Dual",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await dual_repo.finalize_run(
        session_id="sess-1",
        status="incomplete",
        summary={"session_status": "incomplete"},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )

    run = await dual_repo.get_run("sess-1")
    assert run is not None
    assert run["status"] == "incomplete"
    assert dual_repo.__class__.__name__ == "AsyncDualModeLedgerRepository"
    parity_events = [row for row in telemetry if row.get("kind") == "run_ledger_dual_write_parity"]
    assert len(parity_events) >= 2
    assert any(row.get("phase") == "start_run" and row.get("parity_ok") is True for row in parity_events)
    assert any(row.get("phase") == "finalize_run" and row.get("parity_ok") is True for row in parity_events)


class _FailingProtocolRepository:
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
        raise OSError("forced protocol write failure")

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: str | None = None,
        failure_reason: str | None = None,
        summary: dict[str, Any] | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> None:
        raise OSError("forced protocol write failure")

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        return None

    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raise OSError("forced protocol write failure")

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        raise OSError("forced protocol write failure")

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return []


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_degrades_on_protocol_error_and_keeps_sqlite_authoritative(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    telemetry: list[dict[str, Any]] = []
    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=_FailingProtocolRepository(),
        telemetry_sink=lambda payload: telemetry.append(dict(payload)),
    )

    await dual_repo.start_run(
        session_id="sess-error",
        run_type="epic",
        run_name="Dual Error",
        department="core",
        build_id="build-1",
    )
    await dual_repo.finalize_run(
        session_id="sess-error",
        status="failed",
        failure_class="ExecutionFailed",
        failure_reason="forced",
    )

    run = await dual_repo.get_run("sess-error")
    assert run is not None
    assert run["status"] == "failed"
    errors = [row for row in telemetry if row.get("kind") == "run_ledger_dual_write_error"]
    assert len(errors) >= 2
    parity_events = [row for row in telemetry if row.get("kind") == "run_ledger_dual_write_parity"]
    assert any(row.get("parity_ok") is False for row in parity_events)
    assert any(row.get("parity_skip_reason") == "protocol_write_failed" for row in parity_events)
    assert any("OSError:forced protocol write failure" in str(row.get("protocol_error")) for row in parity_events)


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_supports_protocol_primary_reads(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        primary_mode="protocol",
    )
    await dual_repo.start_run(
        session_id="sess-primary",
        run_type="epic",
        run_name="Primary",
        department="core",
        build_id="build-1",
    )
    await dual_repo.finalize_run(
        session_id="sess-primary",
        status="incomplete",
    )
    run = await dual_repo.get_run("sess-primary")
    assert run is not None
    assert run["session_id"] == "sess-primary"
    assert run["status"] == "incomplete"


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_logs_sink_failures_without_interrupting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Layer: unit. Verifies telemetry sink failures stay non-fatal and emit an explicit warning signal."""
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    logged: list[dict[str, Any]] = []

    def _capture_log(event: str, data: dict[str, Any] | None = None, **_: Any) -> None:
        logged.append({"event": event, "data": dict(data or {})})

    def _broken_sink(_payload: dict[str, Any]) -> None:
        raise RuntimeError("forced telemetry sink failure")

    monkeypatch.setattr("orket.adapters.storage.async_dual_write_run_ledger.log_event", _capture_log)
    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        telemetry_sink=_broken_sink,
    )

    await dual_repo.start_run(
        session_id="sess-sink",
        run_type="epic",
        run_name="Sink Failure",
        department="core",
        build_id="build-1",
    )

    assert dual_repo.sink_failure_count >= 1
    assert any(
        row["event"] == "telemetry_sink_error"
        and row["data"].get("error_type") == "RuntimeError"
        for row in logged
    )


class _BrokenProtocolRepository:
    async def start_run(self, **_: Any) -> None:
        raise AttributeError("missing method on protocol repo")

    async def finalize_run(self, **_: Any) -> None:
        raise AttributeError("missing method on protocol repo")

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        _ = session_id
        return None

    async def append_event(self, **_: Any) -> dict[str, Any]:
        raise AttributeError("missing method on protocol repo")

    async def append_receipt(self, **_: Any) -> dict[str, Any]:
        raise AttributeError("missing method on protocol repo")

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        _ = session_id
        return []


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_propagates_structural_protocol_misconfiguration(tmp_path: Path) -> None:
    """Layer: unit. Verifies broken protocol repo wiring fails closed instead of being swallowed as transient I/O drift."""
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=_BrokenProtocolRepository(),
    )

    with pytest.raises(AttributeError, match="missing method on protocol repo"):
        await dual_repo.start_run(
            session_id="sess-bad-struct",
            run_type="epic",
            run_name="Broken Struct",
            department="core",
            build_id="build-1",
        )


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_distinguishes_parity_check_crash_from_parity_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Layer: unit. Verifies parity telemetry distinguishes a comparator crash from a real parity mismatch."""
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    telemetry: list[dict[str, Any]] = []

    async def _boom(**_: Any) -> dict[str, Any]:
        raise RuntimeError("forced parity crash")

    monkeypatch.setattr("orket.adapters.storage.async_dual_write_run_ledger.compare_run_ledger_rows", _boom)
    dual_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        telemetry_sink=lambda payload: telemetry.append(dict(payload)),
    )

    await dual_repo.start_run(
        session_id="sess-parity-crash",
        run_type="epic",
        run_name="Parity Crash",
        department="core",
        build_id="build-1",
    )

    parity_event = next(row for row in telemetry if row.get("kind") == "run_ledger_dual_write_parity")
    assert parity_event["parity_ok"] is False
    assert parity_event["parity_check_error"] is True
    assert "RuntimeError:forced parity crash" in str(parity_event["parity_error"])


class _FinalizeFailingProtocolRepository:
    def __init__(self, delegate: AsyncProtocolRunLedgerRepository) -> None:
        self._delegate = delegate
        self.root = delegate.root

    async def start_run(self, **kwargs: Any) -> None:
        await self._delegate.start_run(**kwargs)

    async def finalize_run(self, **_: Any) -> None:
        raise OSError("forced protocol finalize failure")

    async def get_run(self, session_id: str) -> dict[str, Any] | None:
        return await self._delegate.get_run(session_id)

    async def append_event(self, **kwargs: Any) -> dict[str, Any]:
        return await self._delegate.append_event(**kwargs)

    async def append_receipt(self, **kwargs: Any) -> dict[str, Any]:
        return await self._delegate.append_receipt(**kwargs)

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return await self._delegate.list_events(session_id)


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_recovers_pending_start_intent_before_next_operation(
    tmp_path: Path,
) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    broken_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=_FailingProtocolRepository(),
    )

    await broken_repo.start_run(
        session_id="sess-recover-start",
        run_type="epic",
        run_name="Recover Start",
        department="core",
        build_id="build-1",
    )

    recovered_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=AsyncRunLedgerRepository(tmp_path / "runtime.db"),
        protocol_repo=AsyncProtocolRunLedgerRepository(tmp_path / "workspace"),
    )

    await recovered_repo.start_run(
        session_id="sess-after-recovery",
        run_type="epic",
        run_name="After Recovery",
        department="core",
        build_id="build-2",
    )

    recovered_events = await recovered_repo.list_events("sess-recover-start")
    assert [event["kind"] for event in recovered_events] == ["run_started"]
    recovered_sqlite_run = await recovered_repo.sqlite_repo.get_run("sess-recover-start")
    assert recovered_sqlite_run is not None
    assert recovered_sqlite_run["session_id"] == "sess-recover-start"
    recovered_protocol_run = await recovered_repo.protocol_repo.get_run("sess-recover-start")
    assert recovered_protocol_run is not None
    assert await recovered_repo._load_intents() == []


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_recovers_pending_finalize_intent_before_next_operation(
    tmp_path: Path,
) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    working_protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    broken_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=sqlite_repo,
        protocol_repo=_FinalizeFailingProtocolRepository(working_protocol_repo),
    )

    await broken_repo.start_run(
        session_id="sess-recover-finalize",
        run_type="epic",
        run_name="Recover Finalize",
        department="core",
        build_id="build-1",
    )
    await broken_repo.finalize_run(
        session_id="sess-recover-finalize",
        status="failed",
        failure_class="ExecutionFailed",
        failure_reason="forced finalize recovery",
    )

    recovered_repo = AsyncDualModeLedgerRepository(
        sqlite_repo=AsyncRunLedgerRepository(tmp_path / "runtime.db"),
        protocol_repo=AsyncProtocolRunLedgerRepository(tmp_path / "workspace"),
    )

    await recovered_repo.start_run(
        session_id="sess-recovery-trigger",
        run_type="epic",
        run_name="Recovery Trigger",
        department="core",
        build_id="build-2",
    )

    recovered_run = await recovered_repo.protocol_repo.get_run("sess-recover-finalize")
    assert recovered_run is not None
    assert recovered_run["status"] == "failed"
    assert recovered_run["failure_class"] == "ExecutionFailed"
    recovered_sqlite_run = await recovered_repo.sqlite_repo.get_run("sess-recover-finalize")
    assert recovered_sqlite_run is not None
    assert recovered_sqlite_run["status"] == "failed"
    recovered_events = await recovered_repo.list_events("sess-recover-finalize")
    assert [event["kind"] for event in recovered_events] == ["run_started", "run_finalized"]
    assert await recovered_repo._load_intents() == []
