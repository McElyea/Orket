from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
from pydantic import ValidationError

from orket.core.domain.sandbox_lifecycle import SandboxLifecycleError
from orket.core.domain.sandbox_lifecycle_records import (
    SandboxApprovalRecord,
    SandboxLifecycleEventRecord,
    SandboxLifecycleRecord,
    SandboxOperationDedupeEntry,
)
from orket.adapters.storage.sandbox_lifecycle_row_serialization import (
    deserialize_event_row,
    deserialize_operation_row,
    deserialize_record_row,
)


class SandboxOperationIntegrityError(SandboxLifecycleError):
    """Raised when an operation id is reused with a different payload hash."""


class SandboxLifecycleConflictError(SandboxLifecycleError):
    """Raised when a compare-and-set lifecycle mutation loses its fence."""


class AsyncSandboxLifecycleRepository:
    """Durable SQLite repository for sandbox lifecycle authority."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()

    async def _ensure_initialized(self, conn: aiosqlite.Connection) -> None:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sandbox_lifecycle_records (
                sandbox_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                compose_project TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                run_id TEXT,
                session_id TEXT,
                owner_instance_id TEXT,
                cleanup_owner_instance_id TEXT,
                lease_epoch INTEGER NOT NULL,
                lease_expires_at TEXT,
                state TEXT NOT NULL,
                cleanup_state TEXT NOT NULL,
                record_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_heartbeat_at TEXT,
                terminal_at TEXT,
                terminal_reason TEXT,
                cleanup_due_at TEXT,
                cleanup_attempts INTEGER NOT NULL,
                cleanup_last_error TEXT,
                cleanup_failure_reason TEXT,
                required_evidence_ref TEXT,
                managed_resource_inventory_json TEXT NOT NULL,
                requires_reconciliation INTEGER NOT NULL,
                docker_context TEXT NOT NULL,
                docker_host_id TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sandbox_operation_dedupe (
                operation_id TEXT PRIMARY KEY,
                payload_hash TEXT NOT NULL,
                result_payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sandbox_approvals (
                approval_id TEXT PRIMARY KEY,
                sandbox_id TEXT NOT NULL,
                action TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                reason TEXT,
                created_at TEXT NOT NULL,
                revoked_by TEXT,
                revoked_at TEXT
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sandbox_lifecycle_events (
                event_id TEXT PRIMARY KEY,
                sandbox_id TEXT,
                event_kind TEXT NOT NULL,
                event_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sandbox_approvals_sandbox_id
            ON sandbox_approvals (sandbox_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sandbox_lifecycle_events_sandbox_id
            ON sandbox_lifecycle_events (sandbox_id)
            """
        )

    async def _execute(self, operation, *, row_factory: bool = False, commit: bool = False):
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as conn:
                if row_factory:
                    conn.row_factory = aiosqlite.Row
                await self._ensure_initialized(conn)
                result = await operation(conn)
                if commit:
                    await conn.commit()
                return result

    async def save_record(self, record: SandboxLifecycleRecord) -> None:
        payload = record.model_dump(mode="json")

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT OR REPLACE INTO sandbox_lifecycle_records (
                    sandbox_id, schema_version, policy_version, compose_project, workspace_path,
                    run_id, session_id, owner_instance_id, cleanup_owner_instance_id, lease_epoch, lease_expires_at,
                    state, cleanup_state, record_version, created_at, last_heartbeat_at,
                    terminal_at, terminal_reason, cleanup_due_at, cleanup_attempts,
                    cleanup_last_error, cleanup_failure_reason, required_evidence_ref,
                    managed_resource_inventory_json, requires_reconciliation,
                    docker_context, docker_host_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["sandbox_id"],
                    payload["schema_version"],
                    payload["policy_version"],
                    payload["compose_project"],
                    payload["workspace_path"],
                    payload.get("run_id"),
                    payload.get("session_id"),
                    payload.get("owner_instance_id"),
                    payload.get("cleanup_owner_instance_id"),
                    payload["lease_epoch"],
                    payload.get("lease_expires_at"),
                    payload["state"],
                    payload["cleanup_state"],
                    payload["record_version"],
                    payload["created_at"],
                    payload.get("last_heartbeat_at"),
                    payload.get("terminal_at"),
                    payload.get("terminal_reason"),
                    payload.get("cleanup_due_at"),
                    payload["cleanup_attempts"],
                    payload.get("cleanup_last_error"),
                    payload.get("cleanup_failure_reason"),
                    payload.get("required_evidence_ref"),
                    json.dumps(payload["managed_resource_inventory"], sort_keys=True),
                    1 if payload["requires_reconciliation"] else 0,
                    payload["docker_context"],
                    payload["docker_host_id"],
                ),
            )

        await self._execute(_op, commit=True)

    async def apply_record_mutation(
        self,
        *,
        operation_id: str,
        payload_hash: str,
        record: SandboxLifecycleRecord,
        expected_record_version: int,
        expected_lease_epoch: int | None = None,
        expected_owner_instance_id: str | None = None,
        expected_cleanup_state: str | None = None,
    ) -> dict[str, object]:
        result_payload = {
            "sandbox_id": record.sandbox_id,
            "record_version": record.record_version,
            "state": record.state.value,
            "cleanup_state": record.cleanup_state.value,
            "requires_reconciliation": record.requires_reconciliation,
        }

        async def _op(conn: aiosqlite.Connection) -> dict[str, object]:
            existing_cursor = await conn.execute(
                "SELECT * FROM sandbox_operation_dedupe WHERE operation_id = ?",
                (operation_id,),
            )
            existing = await existing_cursor.fetchone()
            if existing is not None:
                stored = deserialize_operation_row(dict(existing))
                if stored.payload_hash != payload_hash:
                    raise SandboxOperationIntegrityError(
                        f"operation_id {operation_id} reused with different payload hash."
                    )
                return {"reused": True, "result": stored.result_payload}
            where = ["sandbox_id = ?", "record_version = ?"]
            params: list[object] = [record.sandbox_id, expected_record_version]
            if expected_lease_epoch is not None:
                where.append("lease_epoch = ?")
                params.append(expected_lease_epoch)
            if expected_owner_instance_id is not None:
                where.append("owner_instance_id = ?")
                params.append(expected_owner_instance_id)
            if expected_cleanup_state is not None:
                where.append("cleanup_state = ?")
                params.append(expected_cleanup_state)
            payload = record.model_dump(mode="json")
            update_cursor = await conn.execute(
                f"""
                UPDATE sandbox_lifecycle_records
                SET schema_version = ?, policy_version = ?, compose_project = ?, workspace_path = ?,
                    run_id = ?, session_id = ?, owner_instance_id = ?, cleanup_owner_instance_id = ?,
                    lease_epoch = ?, lease_expires_at = ?, state = ?, cleanup_state = ?, record_version = ?,
                    created_at = ?, last_heartbeat_at = ?, terminal_at = ?, terminal_reason = ?, cleanup_due_at = ?,
                    cleanup_attempts = ?, cleanup_last_error = ?,
                    cleanup_failure_reason = ?, required_evidence_ref = ?,
                    managed_resource_inventory_json = ?, requires_reconciliation = ?,
                    docker_context = ?, docker_host_id = ?
                WHERE {" AND ".join(where)}
                """,
                (
                    payload["schema_version"],
                    payload["policy_version"],
                    payload["compose_project"],
                    payload["workspace_path"],
                    payload.get("run_id"),
                    payload.get("session_id"),
                    payload.get("owner_instance_id"),
                    payload.get("cleanup_owner_instance_id"),
                    payload["lease_epoch"],
                    payload.get("lease_expires_at"),
                    payload["state"],
                    payload["cleanup_state"],
                    payload["record_version"],
                    payload["created_at"],
                    payload.get("last_heartbeat_at"),
                    payload.get("terminal_at"),
                    payload.get("terminal_reason"),
                    payload.get("cleanup_due_at"),
                    payload["cleanup_attempts"],
                    payload.get("cleanup_last_error"),
                    payload.get("cleanup_failure_reason"),
                    payload.get("required_evidence_ref"),
                    json.dumps(payload["managed_resource_inventory"], sort_keys=True),
                    1 if payload["requires_reconciliation"] else 0,
                    payload["docker_context"],
                    payload["docker_host_id"],
                    *params,
                ),
            )
            if update_cursor.rowcount <= 0:
                raise SandboxLifecycleConflictError(f"CAS update rejected for sandbox_id {record.sandbox_id}.")
            await conn.execute(
                """
                INSERT INTO sandbox_operation_dedupe (
                    operation_id, payload_hash, result_payload_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    operation_id,
                    payload_hash,
                    json.dumps(result_payload, sort_keys=True),
                    record.created_at,
                ),
            )
            return {"reused": False, "result": result_payload}

        return await self._execute(_op, row_factory=True, commit=True)

    async def get_record(self, sandbox_id: str) -> SandboxLifecycleRecord | None:
        async def _op(conn: aiosqlite.Connection) -> SandboxLifecycleRecord | None:
            cursor = await conn.execute(
                "SELECT * FROM sandbox_lifecycle_records WHERE sandbox_id = ?",
                (sandbox_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            try:
                return SandboxLifecycleRecord.model_validate(deserialize_record_row(dict(row)))
            except ValidationError as exc:
                raise SandboxLifecycleError(str(exc)) from exc

        return await self._execute(_op, row_factory=True)

    async def list_records(self) -> list[SandboxLifecycleRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[SandboxLifecycleRecord]:
            cursor = await conn.execute(
                "SELECT * FROM sandbox_lifecycle_records ORDER BY datetime(created_at) ASC, sandbox_id ASC"
            )
            rows = await cursor.fetchall()
            try:
                return [SandboxLifecycleRecord.model_validate(deserialize_record_row(dict(row))) for row in rows]
            except ValidationError as exc:
                raise SandboxLifecycleError(str(exc)) from exc

        return await self._execute(_op, row_factory=True)

    async def remember_operation(
        self,
        entry: SandboxOperationDedupeEntry,
    ) -> SandboxOperationDedupeEntry:
        async def _op(conn: aiosqlite.Connection) -> SandboxOperationDedupeEntry:
            cursor = await conn.execute(
                "SELECT * FROM sandbox_operation_dedupe WHERE operation_id = ?",
                (entry.operation_id,),
            )
            existing = await cursor.fetchone()
            if existing is None:
                await conn.execute(
                    """
                    INSERT INTO sandbox_operation_dedupe (
                        operation_id, payload_hash, result_payload_json, created_at
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        entry.operation_id,
                        entry.payload_hash,
                        json.dumps(entry.result_payload, sort_keys=True),
                        entry.created_at,
                    ),
                )
                return entry
            stored = deserialize_operation_row(dict(existing))
            if stored.payload_hash != entry.payload_hash:
                raise SandboxOperationIntegrityError(
                    f"operation_id {entry.operation_id} reused with different payload hash."
                )
            return stored

        return await self._execute(_op, row_factory=True, commit=True)

    async def save_approval(self, record: SandboxApprovalRecord) -> None:
        payload = record.model_dump(mode="json")

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT OR REPLACE INTO sandbox_approvals (
                    approval_id, sandbox_id, action, approved_by, reason, created_at, revoked_by, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["approval_id"],
                    payload["sandbox_id"],
                    payload["action"],
                    payload["approved_by"],
                    payload.get("reason"),
                    payload["created_at"],
                    payload.get("revoked_by"),
                    payload.get("revoked_at"),
                ),
            )

        await self._execute(_op, commit=True)

    async def list_approvals(self, sandbox_id: str) -> list[SandboxApprovalRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[SandboxApprovalRecord]:
            cursor = await conn.execute(
                """
                SELECT * FROM sandbox_approvals
                WHERE sandbox_id = ?
                ORDER BY datetime(created_at) ASC, approval_id ASC
                """,
                (sandbox_id,),
            )
            rows = await cursor.fetchall()
            return [SandboxApprovalRecord.model_validate(dict(row)) for row in rows]

        return await self._execute(_op, row_factory=True)

    async def revoke_approval(self, approval_id: str, *, revoked_by: str, revoked_at: str) -> bool:
        async def _op(conn: aiosqlite.Connection) -> bool:
            cursor = await conn.execute(
                """
                UPDATE sandbox_approvals
                SET revoked_by = ?, revoked_at = ?
                WHERE approval_id = ?
                """,
                (revoked_by, revoked_at, approval_id),
            )
            return cursor.rowcount > 0

        return await self._execute(_op, commit=True)

    async def append_event(self, record: SandboxLifecycleEventRecord) -> None:
        payload = record.model_dump(mode="json")

        async def _op(conn: aiosqlite.Connection) -> None:
            await conn.execute(
                """
                INSERT OR REPLACE INTO sandbox_lifecycle_events (
                    event_id, sandbox_id, event_kind, event_type, created_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["event_id"],
                    payload.get("sandbox_id"),
                    payload["event_kind"],
                    payload["event_type"],
                    payload["created_at"],
                    json.dumps(payload["payload"], sort_keys=True),
                ),
            )

        await self._execute(_op, commit=True)

    async def list_events(self, sandbox_id: str | None = None) -> list[SandboxLifecycleEventRecord]:
        async def _op(conn: aiosqlite.Connection) -> list[SandboxLifecycleEventRecord]:
            if sandbox_id:
                cursor = await conn.execute(
                    """
                    SELECT * FROM sandbox_lifecycle_events
                    WHERE sandbox_id = ?
                    ORDER BY datetime(created_at) ASC, event_id ASC
                    """,
                    (sandbox_id,),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM sandbox_lifecycle_events ORDER BY datetime(created_at) ASC, event_id ASC"
                )
            rows = await cursor.fetchall()
            return [SandboxLifecycleEventRecord.model_validate(deserialize_event_row(dict(row))) for row in rows]

        return await self._execute(_op, row_factory=True)
