# LIFECYCLE: live
from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from scripts.protocol.run_protocol_ledger_parity_campaign import main


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


def test_run_protocol_ledger_parity_campaign_reports_clean_match(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    out = tmp_path / "campaign.json"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )

    exit_code = main(
        [
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["all_match"] is True
    assert payload["mismatch_count"] == 0


def test_run_protocol_ledger_parity_campaign_strict_fails_when_mismatches_exceed_threshold(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="failed",
            protocol_status="incomplete",
        )
    )

    exit_code = main(
        [
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--strict",
            "--max-mismatches",
            "0",
        ]
    )
    assert exit_code == 1


def test_run_protocol_ledger_parity_campaign_non_strict_allows_mismatch(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    asyncio.run(
        _seed_run(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="failed",
            protocol_status="incomplete",
        )
    )

    exit_code = main(
        [
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
        ]
    )
    assert exit_code == 0


def test_run_protocol_ledger_parity_campaign_preserves_invalid_projection_fields(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "workspace"
    out = tmp_path / "campaign-invalid.json"
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

    exit_code = main(
        [
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--session-id",
            "sess-invalid",
            "--out",
            str(out),
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["rows"][0]["sqlite_invalid_projection_fields"] == ["summary_json", "artifact_json"]
    assert payload["compatibility_telemetry_delta"]["sqlite_invalid_projection_field_counts"] == {
        "artifact_json": 1,
        "summary_json": 1,
    }
