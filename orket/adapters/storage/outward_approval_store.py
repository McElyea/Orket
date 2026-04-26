from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigration, SQLiteMigrationRunner
from orket.core.domain.outward_approvals import OutwardApprovalProposal

_MIGRATIONS = [
    SQLiteMigration(
        version=1,
        name="create_outward_approvals",
        statements=(
            """
            CREATE TABLE IF NOT EXISTS outward_approval_proposals (
                proposal_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                namespace TEXT NOT NULL,
                tool TEXT NOT NULL,
                args_preview_json TEXT NOT NULL,
                context_summary TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                submitted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL,
                operator_ref TEXT,
                decision TEXT,
                reason TEXT,
                note TEXT,
                decided_at TEXT
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_outward_approvals_status_expires ON outward_approval_proposals (status, expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_outward_approvals_run ON outward_approval_proposals (run_id)",
        ),
    )
]


class OutwardApprovalStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            async with connect_sqlite_wal(self.db_path) as conn:
                await SQLiteMigrationRunner(namespace="outward_approvals").apply(conn, _MIGRATIONS)
                await conn.commit()
            self._initialized = True

    async def save(self, proposal: OutwardApprovalProposal) -> OutwardApprovalProposal:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            await conn.execute(
                """
                INSERT OR REPLACE INTO outward_approval_proposals (
                    proposal_id, run_id, namespace, tool, args_preview_json, context_summary,
                    risk_level, submitted_at, expires_at, status, operator_ref, decision,
                    reason, note, decided_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _proposal_params(proposal),
            )
            await conn.commit()
        return proposal

    async def get(self, proposal_id: str) -> OutwardApprovalProposal | None:
        await self.ensure_initialized()
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM outward_approval_proposals WHERE proposal_id = ?",
                (proposal_id,),
            )
            row = await cursor.fetchone()
        return _row_to_proposal(row) if row is not None else None

    async def list(
        self,
        *,
        status: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[OutwardApprovalProposal]:
        await self.ensure_initialized()
        limit = max(1, min(int(limit), 500))
        conditions: list[str] = []
        params: list[Any] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if run_id:
            conditions.append("run_id = ?")
            params.append(run_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT * FROM outward_approval_proposals
            {where}
            ORDER BY expires_at ASC, submitted_at ASC, proposal_id ASC
            LIMIT ?
        """
        params.append(limit)
        async with connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, tuple(params))
            rows = await cursor.fetchall()
        return [_row_to_proposal(row) for row in rows]


def _proposal_params(proposal: OutwardApprovalProposal) -> tuple[Any, ...]:
    return (
        proposal.proposal_id,
        proposal.run_id,
        proposal.namespace,
        proposal.tool,
        _json(proposal.args_preview),
        proposal.context_summary,
        proposal.risk_level,
        proposal.submitted_at,
        proposal.expires_at,
        proposal.status,
        proposal.operator_ref,
        proposal.decision,
        proposal.reason,
        proposal.note,
        proposal.decided_at,
    )


def _json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _row_to_proposal(row: aiosqlite.Row) -> OutwardApprovalProposal:
    return OutwardApprovalProposal(
        proposal_id=str(row["proposal_id"]),
        run_id=str(row["run_id"]),
        namespace=str(row["namespace"]),
        tool=str(row["tool"]),
        args_preview=dict(json.loads(str(row["args_preview_json"]))),
        context_summary=str(row["context_summary"]),
        risk_level=str(row["risk_level"]),
        submitted_at=str(row["submitted_at"]),
        expires_at=str(row["expires_at"]),
        status=str(row["status"]),
        operator_ref=row["operator_ref"],
        decision=row["decision"],
        reason=row["reason"],
        note=row["note"],
        decided_at=row["decided_at"],
    )


__all__ = ["OutwardApprovalStore"]
