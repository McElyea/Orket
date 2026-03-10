from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_dual_write_run_ledger import AsyncDualWriteRunLedgerRepository
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

    dual_repo = AsyncDualWriteRunLedgerRepository(
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
    dual_repo = AsyncDualWriteRunLedgerRepository(
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
    assert any("OSError:forced protocol write failure" in str(row.get("protocol_error")) for row in parity_events)


@pytest.mark.asyncio
async def test_async_dual_write_run_ledger_supports_protocol_primary_reads(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "workspace")
    dual_repo = AsyncDualWriteRunLedgerRepository(
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
