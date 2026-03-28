from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.runtime.protocol_ledger_parity_campaign import compare_protocol_ledger_parity_campaign


async def _seed_run(
    *,
    sqlite_db: Path,
    protocol_root: Path,
    session_id: str,
    sqlite_status: str,
    protocol_status: str,
) -> None:
    sqlite_repo = AsyncRunLedgerRepository(sqlite_db)
    protocol_repo = AsyncProtocolRunLedgerRepository(protocol_root)
    await sqlite_repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Parity Campaign",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await sqlite_repo.finalize_run(
        session_id=session_id,
        status=sqlite_status,
        summary={"session_status": sqlite_status},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )
    await protocol_repo.start_run(
        session_id=session_id,
        run_type="epic",
        run_name="Parity Campaign",
        department="core",
        build_id="build-1",
        summary={"session_status": "running"},
        artifacts={"workspace": "workspace/default"},
    )
    await protocol_repo.finalize_run(
        session_id=session_id,
        status=protocol_status,
        summary={"session_status": protocol_status},
        artifacts={"gitea_export": {"provider": "gitea"}},
    )


def test_protocol_ledger_parity_campaign_reports_clean_match(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )

    payload = asyncio.run(
        compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_ids=[],
            discover_limit=50,
        )
    )
    assert payload["all_match"] is True
    assert payload["mismatch_count"] == 0
    assert payload["candidate_count"] == 1
    assert payload["compatibility_telemetry_delta"]["field_delta_counts"] == {}


def test_protocol_ledger_parity_campaign_detects_mismatch_and_reports_deltas(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="failed",
        )
    )

    payload = asyncio.run(
        compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_ids=["sess-1"],
            discover_limit=50,
        )
    )
    assert payload["all_match"] is False
    assert payload["mismatch_count"] == 1
    assert payload["mismatches"][0]["session_id"] == "sess-1"
    fields = payload["compatibility_telemetry_delta"]["field_delta_counts"]
    assert fields.get("status", 0) >= 1
    signatures = payload["compatibility_telemetry_delta"]["status_delta_counts"]
    assert signatures.get("status:incomplete->failed", 0) >= 1


def test_protocol_ledger_parity_campaign_preserves_invalid_projection_fields(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-invalid",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )
    with sqlite3.connect(sqlite_db) as conn:
        conn.execute(
            "UPDATE run_ledger SET summary_json = ?, artifact_json = ? WHERE session_id = ?",
            ("{not-json", "[1,2,3]", "sess-invalid"),
        )
        conn.commit()

    payload = asyncio.run(
        compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_ids=["sess-invalid"],
            discover_limit=50,
        )
    )
    assert payload["all_match"] is False
    assert payload["rows"][0]["sqlite_invalid_projection_fields"] == ["summary_json", "artifact_json"]
    assert payload["rows"][0]["protocol_invalid_projection_fields"] == []
    assert payload["mismatches"][0]["sqlite_invalid_projection_fields"] == ["summary_json", "artifact_json"]
    telemetry = payload["compatibility_telemetry_delta"]["sqlite_invalid_projection_field_counts"]
    assert telemetry == {"artifact_json": 1, "summary_json": 1}
    assert payload["compatibility_telemetry_delta"]["protocol_invalid_projection_field_counts"] == {}


def test_protocol_ledger_parity_campaign_filters_to_requested_session_ids(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-2",
            sqlite_status="failed",
            protocol_status="failed",
        )
    )

    payload = asyncio.run(
        compare_protocol_ledger_parity_campaign(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_ids=["sess-2"],
            discover_limit=50,
        )
    )
    assert payload["candidate_count"] == 1
    assert payload["rows"][0]["session_id"] == "sess-2"


def test_protocol_ledger_parity_campaign_raises_when_no_sessions_available(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "missing.db"
    protocol_root = tmp_path / "workspace"
    with pytest.raises(ValueError) as exc:
        asyncio.run(
            compare_protocol_ledger_parity_campaign(
                sqlite_db=sqlite_db,
                protocol_root=protocol_root,
                session_ids=[],
                discover_limit=10,
            )
        )
    assert "No session ids available" in str(exc.value)
