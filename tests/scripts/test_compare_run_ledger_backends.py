# LIFECYCLE: live
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from scripts.protocol.compare_run_ledger_backends import main


async def _seed_ledgers(
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
        run_name="Parity",
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
        run_name="Parity",
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


def test_compare_run_ledger_backends_writes_parity_report(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "protocol"
    out_path = tmp_path / "parity.json"
    asyncio.run(
        _seed_ledgers(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )

    exit_code = main(
        [
            "--session-id",
            "sess-1",
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--out",
            str(out_path),
            "--strict",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["parity_ok"] is True
    assert payload["differences"] == []


def test_compare_run_ledger_backends_strict_fails_on_mismatch(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "protocol"
    asyncio.run(
        _seed_ledgers(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="incomplete",
            protocol_status="failed",
        )
    )

    exit_code = main(
        [
            "--session-id",
            "sess-1",
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--strict",
        ]
    )
    assert exit_code == 1


def test_compare_run_ledger_backends_non_strict_returns_zero_on_mismatch(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "protocol"
    asyncio.run(
        _seed_ledgers(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-1",
            sqlite_status="failed",
            protocol_status="incomplete",
        )
    )

    exit_code = main(
        [
            "--session-id",
            "sess-1",
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
        ]
    )
    assert exit_code == 0


def test_compare_run_ledger_backends_strict_fails_on_invalid_projection_payload(tmp_path: Path) -> None:
    sqlite_db = tmp_path / "runtime.db"
    protocol_root = tmp_path / "protocol"
    out_path = tmp_path / "parity-invalid.json"
    asyncio.run(
        _seed_ledgers(
            sqlite_db=sqlite_db,
            protocol_root=protocol_root,
            session_id="sess-invalid",
            sqlite_status="incomplete",
            protocol_status="incomplete",
        )
    )

    import sqlite3

    with sqlite3.connect(sqlite_db) as conn:
        conn.execute(
            "UPDATE run_ledger SET summary_json = ?, artifact_json = ? WHERE session_id = ?",
            ("{not-json", "[1,2,3]", "sess-invalid"),
        )
        conn.commit()

    exit_code = main(
        [
            "--session-id",
            "sess-invalid",
            "--sqlite-db",
            str(sqlite_db),
            "--protocol-root",
            str(protocol_root),
            "--out",
            str(out_path),
            "--strict",
        ]
    )
    assert exit_code == 1
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["parity_ok"] is False
    assert payload["sqlite_invalid_projection_fields"] == ["summary_json", "artifact_json"]
    assert any(row["field"] == "__projection_validation__" for row in payload["differences"])
