"""Read old binding evidence without initializing or modifying historical stores."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite

from orket.adapters.storage.epic_approval_pause_store import EpicApprovalPauseStore
from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.adapters.storage.sqlite_connection import sqlite_connection_scope
from orket.core.contracts.control_plane_models import ResolvedConfigurationSnapshot, RunRecord
from orket.core.contracts.runtime_store_binding import RuntimeStoreMigrationBinding

side_effecting = True


class RuntimeStoreBindingRepository:
    side_effecting = True

    def __init__(self, runtime_db: Path, control_plane_db: Path):
        self.runtime_db, self.control_plane_db = runtime_db, control_plane_db
        self.journal_db = SQLiteEpicPublicationRepository(runtime_db).db_path

    async def admissions(self) -> list[tuple[str, str, str]]:
        if not await asyncio.to_thread(self.journal_db.is_file):
            return []
        async with aiosqlite.connect(self.journal_db.as_uri() + "?mode=ro", uri=True) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in await cursor.fetchall()}
            if "epic_run_admissions" not in tables:
                if tables & {"epic_publications", "epic_preparations", "epic_approval_pauses"}:
                    raise ValueError("E_RUNTIME_STORE_ADMISSION_HISTORY_MISSING")
                return []
            cursor = await conn.execute(
                "SELECT session_id, payload, digest FROM epic_run_admissions ORDER BY session_id"
            )
            rows = list(await cursor.fetchall())
            sessions = {row[0] for row in rows}
            for table in ("epic_publications", "epic_preparations", "epic_workload_outcomes", "epic_approval_pauses"):
                if table in tables:
                    cursor = await conn.execute("SELECT DISTINCT session_id FROM " + table)
                    if any(row[0] not in sessions for row in await cursor.fetchall()):
                        raise ValueError("E_RUNTIME_STORE_ADMISSION_HISTORY_MISSING")
            return rows

    async def approval_pause(self, session_id: str):
        async with aiosqlite.connect(self.journal_db.as_uri() + "?mode=ro", uri=True) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='epic_approval_pauses'"
            )
            if await cursor.fetchone() is None:
                return None
            return await EpicApprovalPauseStore(conn, session_id).latest()

    async def read_binding(self, path: Path) -> RuntimeStoreMigrationBinding | None:
        if not await asyncio.to_thread(path.is_file):
            return None
        async with aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_store_bindings'"
            )
            if await cursor.fetchone() is None:
                return None
            cursor = await conn.execute(
                "SELECT payload, digest FROM runtime_store_bindings WHERE runtime_db=?", (str(self.runtime_db),)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            binding = RuntimeStoreMigrationBinding.model_validate_json(row[0])
            if binding.digest() != row[1]:
                raise ValueError("E_RUNTIME_STORE_BINDING_INTEGRITY")
            return binding

    async def approval_targets(self, session_ids: set[str]) -> set[str]:
        async with aiosqlite.connect(self.runtime_db.as_uri() + "?mode=ro", uri=True) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='pending_gate_requests'"
            )
            if await cursor.fetchone() is None:
                return set()
            cursor = await conn.execute("SELECT session_id, payload_json FROM pending_gate_requests")
            targets = set()
            for session_id, payload in await cursor.fetchall():
                if session_id in session_ids:
                    target = json.loads(payload or "{}").get("control_plane_target_ref")
                    if not isinstance(target, str) or not target:
                        raise ValueError("E_RUNTIME_STORE_MIGRATION_APPROVAL_TARGET_MISSING")
                    targets.add(target)
            return targets

    async def run_configurations(self, path: Path) -> list[tuple[RunRecord, ResolvedConfigurationSnapshot]]:
        async with aiosqlite.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
            cursor = await conn.execute("SELECT run_id, payload_json FROM control_plane_runs")
            records = []
            for run_id, payload in await cursor.fetchall():
                run = RunRecord.model_validate_json(payload)
                row = await (
                    await conn.execute(
                        "SELECT payload_json FROM resolved_configuration_snapshots WHERE snapshot_id=?",
                        (run.configuration_snapshot_id,),
                    )
                ).fetchone()
                if run.run_id != run_id or row is None:
                    raise ValueError("E_RUNTIME_STORE_MIGRATION_RUN_HISTORY_CONFLICT")
                records.append((run, ResolvedConfigurationSnapshot.model_validate_json(row[0])))
            return records

    async def save_binding(
        self, path: Path, binding: RuntimeStoreMigrationBinding, *, connection: aiosqlite.Connection | None = None
    ) -> None:
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        async with sqlite_connection_scope(path, connection, commit=True) as conn:
            if not conn.in_transaction:
                await conn.execute("BEGIN IMMEDIATE")
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS runtime_store_bindings ("
                "runtime_db TEXT PRIMARY KEY, payload TEXT NOT NULL, digest TEXT NOT NULL)"
            )
            cursor = await conn.execute(
                "SELECT payload, digest FROM runtime_store_bindings WHERE runtime_db=?", (binding.runtime_db,)
            )
            previous = await cursor.fetchone()
            if previous is not None:
                if (
                    RuntimeStoreMigrationBinding.model_validate_json(previous[0]) != binding
                    or previous[1] != binding.digest()
                ):
                    raise ValueError("E_RUNTIME_STORE_BINDING_CONFLICT")
            else:
                await conn.execute(
                    "INSERT INTO runtime_store_bindings(runtime_db, payload, digest) VALUES (?, ?, ?)",
                    (binding.runtime_db, binding.model_dump_json(), binding.digest()),
                )
