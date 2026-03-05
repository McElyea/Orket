from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.run_ledger_parity import compare_run_ledger_rows


class _Repo:
    def __init__(self, row: dict[str, Any] | None):
        self._row = row

    async def get_run(self, _session_id: str) -> dict[str, Any] | None:
        return self._row


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_reports_parity_for_identical_rows() -> None:
    row = {
        "session_id": "sess-1",
        "run_type": "epic",
        "run_name": "A",
        "department": "core",
        "build_id": "build-1",
        "status": "incomplete",
        "failure_class": None,
        "failure_reason": None,
        "summary_json": {"session_status": "incomplete"},
        "artifact_json": {"workspace": "workspace/default"},
    }
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(row),
        protocol_repo=_Repo(dict(row)),
        session_id="sess-1",
    )
    assert result["parity_ok"] is True
    assert result["differences"] == []
    assert result["sqlite_digest"] == result["protocol_digest"]


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_reports_field_differences() -> None:
    sqlite_row = {
        "session_id": "sess-1",
        "run_type": "epic",
        "run_name": "A",
        "department": "core",
        "build_id": "build-1",
        "status": "incomplete",
        "failure_class": None,
        "failure_reason": None,
        "summary_json": {"session_status": "incomplete"},
        "artifact_json": {},
    }
    protocol_row = dict(sqlite_row)
    protocol_row["status"] = "failed"
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(sqlite_row),
        protocol_repo=_Repo(protocol_row),
        session_id="sess-1",
    )
    assert result["parity_ok"] is False
    assert any(row["field"] == "status" for row in result["differences"])
    assert result["sqlite_digest"] != result["protocol_digest"]


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_reports_missing_rows() -> None:
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(None),
        protocol_repo=_Repo({"session_id": "sess-1", "status": "incomplete"}),
        session_id="sess-1",
    )
    assert result["parity_ok"] is False
    assert result["differences"][0]["field"] == "__row__"


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_with_real_repositories(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "protocol")
    await sqlite_repo.start_run(
        session_id="sess-real",
        run_type="epic",
        run_name="Protocol",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await sqlite_repo.finalize_run(
        session_id="sess-real",
        status="incomplete",
        summary={"session_status": "incomplete"},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )
    await protocol_repo.start_run(
        session_id="sess-real",
        run_type="epic",
        run_name="Protocol",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await protocol_repo.finalize_run(
        session_id="sess-real",
        status="incomplete",
        summary={"session_status": "incomplete"},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )
    result = await compare_run_ledger_rows(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        session_id="sess-real",
    )
    assert result["parity_ok"] is True
    assert result["differences"] == []


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_missing_both_is_clean() -> None:
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(None),
        protocol_repo=_Repo(None),
        session_id="missing",
    )
    assert result["parity_ok"] is True
    assert result["differences"] == []
    assert result["sqlite_digest"] is None
    assert result["protocol_digest"] is None


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_normalizes_sparse_shapes() -> None:
    sqlite_row = {
        "id": "sess-alt",
        "run_type": "epic",
        "run_name": "Alt",
        "department": "core",
        "build_id": "build-alt",
        "status": "incomplete",
        "summary_json": '{"ignored":"string-shape"}',
        "artifact_json": '{"ignored":"string-shape"}',
    }
    protocol_row = {
        "session_id": "sess-alt",
        "run_type": "epic",
        "run_name": "Alt",
        "department": "core",
        "build_id": "build-alt",
        "status": "incomplete",
        "summary_json": {},
        "artifact_json": {},
    }
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(sqlite_row),
        protocol_repo=_Repo(protocol_row),
        session_id="sess-alt",
    )
    assert result["parity_ok"] is True
    assert result["differences"] == []


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_detects_missing_protocol_row_with_real_sqlite(tmp_path: Path) -> None:
    sqlite_repo = AsyncRunLedgerRepository(tmp_path / "runtime.db")
    protocol_repo = AsyncProtocolRunLedgerRepository(tmp_path / "protocol")
    await sqlite_repo.start_run(
        session_id="sess-only-sqlite",
        run_type="epic",
        run_name="Only SQLite",
        department="core",
        build_id="build-1",
    )
    await sqlite_repo.finalize_run(
        session_id="sess-only-sqlite",
        status="incomplete",
    )
    result = await compare_run_ledger_rows(
        sqlite_repo=sqlite_repo,
        protocol_repo=protocol_repo,
        session_id="sess-only-sqlite",
    )
    assert result["parity_ok"] is False
    assert result["differences"][0]["field"] == "__row__"
    assert result["protocol_row"] is None


@pytest.mark.asyncio
async def test_compare_run_ledger_rows_digest_changes_when_summary_changes() -> None:
    base = {
        "session_id": "sess-1",
        "run_type": "epic",
        "run_name": "A",
        "department": "core",
        "build_id": "build-1",
        "status": "incomplete",
        "summary_json": {"session_status": "incomplete"},
        "artifact_json": {},
    }
    updated = dict(base)
    updated["summary_json"] = {"session_status": "failed"}
    result = await compare_run_ledger_rows(
        sqlite_repo=_Repo(base),
        protocol_repo=_Repo(updated),
        session_id="sess-1",
    )
    assert result["parity_ok"] is False
    assert result["sqlite_digest"] != result["protocol_digest"]
