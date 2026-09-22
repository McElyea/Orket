from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.storage.outward_approval_migrations import OUTWARD_APPROVAL_MIGRATIONS
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal, sqlite_connection_scope
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.core.domain.outward_approvals import OutwardApprovalProposal

side_effecting = True


class OutwardApprovalStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def ensure_initialized(self) -> None:
        async with self._init_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self.db_path.parent.mkdir, parents=True, exist_ok=True)
            async with connect_sqlite_wal(self.db_path) as conn:
                await conn.execute("BEGIN IMMEDIATE")
                cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'outward_approval_proposals'")
                if await cursor.fetchone() is not None:
                    cursor = await conn.execute("SELECT COUNT(*) FROM outward_approval_proposals")
                    if int((await cursor.fetchone())[0]):
                        raise RuntimeError("E_OUTWARD_OFFLINE_APPROVAL_MIGRATION_REQUIRED")
                await SQLiteMigrationRunner(namespace="outward_approvals").apply(conn, OUTWARD_APPROVAL_MIGRATIONS)
                await conn.commit()
            self._initialized = True

    async def save(
        self, proposal: OutwardApprovalProposal, *, connection: aiosqlite.Connection | None = None,
    ) -> OutwardApprovalProposal:
        _ = proposal.authorization
        await self.ensure_initialized()
        async with sqlite_connection_scope(self.db_path, connection) as conn:
            await conn.execute(
                """
                INSERT INTO outward_approval_proposals_v2 (
                    proposal_id, run_id, namespace, tool, args_preview_json, context_summary,
                    risk_level, submitted_at, expires_at, status, operator_ref, decision,
                    reason, note, decided_at, authorization_json, authorization_digest
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _proposal_params(proposal),
            )
        return proposal

    async def get(
        self, proposal_id: str, *, connection: aiosqlite.Connection | None = None,
    ) -> OutwardApprovalProposal | None:
        await self.ensure_initialized()
        async with sqlite_connection_scope(self.db_path, connection) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM outward_approval_proposals_v2 WHERE proposal_id = ?",
                (proposal_id,),
            )
            row = await cursor.fetchone()
        return _row_to_proposal(row) if row is not None else None

    async def count_for_run(self, run_id: str, *, connection: aiosqlite.Connection) -> int:
        cursor = await connection.execute(
            "SELECT COUNT(*) FROM outward_approval_proposals_v2 WHERE run_id = ?", (run_id,),
        )
        return int((await cursor.fetchone())[0])

    async def update_decision(self, proposal: OutwardApprovalProposal, *, connection: aiosqlite.Connection) -> bool:
        cursor = await connection.execute(
            """UPDATE outward_approval_proposals_v2
               SET status = ?, operator_ref = ?, decision = ?, reason = ?, note = ?, decided_at = ?
               WHERE proposal_id = ? AND status = 'pending'""",
            (proposal.status, proposal.operator_ref, proposal.decision, proposal.reason,
             proposal.note, proposal.decided_at, proposal.proposal_id),
        )
        return cursor.rowcount == 1

    async def list(
        self,
        *,
        status: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
        bound_only: bool = False,
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
        if bound_only:
            conditions.append("(authorization_json IS NOT NULL OR authorization_digest IS NOT NULL)")
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        sql = f"""
            SELECT * FROM outward_approval_proposals_v2
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
        proposal.authorization_json,
        proposal.authorization_digest,
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
        authorization_json=row["authorization_json"],
        authorization_digest=row["authorization_digest"],
    )


__all__ = ["OutwardApprovalStore"]
