from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import aiosqlite

from orket.adapters.storage.governed_agent_wake_repository_support import (
    claim_identity_matches,
    claim_matches,
    claim_next_transaction,
    enqueue_transaction,
    ensure_schema,
    get_wake,
    optional_wake,
    required_text,
    required_wake,
    utc_timestamp,
    wake_record,
    wake_row,
)
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeAuthority,
    GovernedAgentWakeClaimResult,
    GovernedAgentWakeEnqueueResult,
    GovernedAgentWakeRecord,
    GovernedAgentWakeRequest,
    GovernedAgentWakeTransitionResult,
)

ResultT = TypeVar("ResultT")


class AsyncGovernedAgentWakeRepository:
    """Durable CAS queue for bounded governed-agent wake ownership."""

    side_effecting = True

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def enqueue(self, request: GovernedAgentWakeRequest) -> GovernedAgentWakeEnqueueResult:
        return await self._execute(lambda conn: enqueue_transaction(conn, request))

    async def claim_next(
        self,
        *,
        owner_id: str,
        now_utc: str,
        lease_expires_at_utc: str,
        max_active_claims: int,
    ) -> GovernedAgentWakeClaimResult:
        owner = required_text(owner_id, "E_AGENT_WAKE_OWNER_REQUIRED")
        now = utc_timestamp(now_utc)
        lease_expiry = utc_timestamp(lease_expires_at_utc)
        if lease_expiry <= now or max_active_claims < 1:
            raise ValueError("E_AGENT_WAKE_CLAIM_BOUNDS_INVALID")
        return await self._execute(
            lambda conn: claim_next_transaction(
                conn,
                owner=owner,
                now=now,
                lease_expiry=lease_expiry,
                max_active_claims=max_active_claims,
            )
        )

    async def validate_claim(self, *, authority: GovernedAgentWakeAuthority, now_utc: str) -> bool:
        now = utc_timestamp(now_utc)

        async def _op(conn: aiosqlite.Connection) -> bool:
            row = await wake_row(conn, authority.wake_id)
            return row is not None and claim_matches(row, authority, now)

        return await self._execute(_op)

    async def renew_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        lease_expires_at_utc: str,
    ) -> GovernedAgentWakeTransitionResult:
        now = utc_timestamp(now_utc)
        lease_expiry = utc_timestamp(lease_expires_at_utc)
        if lease_expiry <= now:
            raise ValueError("E_AGENT_WAKE_LEASE_EXPIRY_INVALID")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWakeTransitionResult:
            await conn.execute("BEGIN IMMEDIATE")
            row = await wake_row(conn, authority.wake_id)
            if row is None or not claim_matches(row, authority, now):
                return GovernedAgentWakeTransitionResult("stale", optional_wake(row))
            if str(row["lease_expires_at_utc"]) == lease_expiry:
                return GovernedAgentWakeTransitionResult("idempotent", wake_record(row))
            await conn.execute(
                "UPDATE governed_agent_wakes SET lease_expires_at_utc = ? WHERE wake_id = ?",
                (lease_expiry, authority.wake_id),
            )
            return GovernedAgentWakeTransitionResult("applied", await required_wake(conn, authority.wake_id))

        return await self._execute(_op)

    async def complete_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        result_ref: str,
    ) -> GovernedAgentWakeTransitionResult:
        now = utc_timestamp(now_utc)
        result = required_text(result_ref, "E_AGENT_WAKE_RESULT_REF_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWakeTransitionResult:
            await conn.execute("BEGIN IMMEDIATE")
            row = await wake_row(conn, authority.wake_id)
            if row is None:
                return GovernedAgentWakeTransitionResult("stale", None)
            if (
                str(row["state"]) == "completed"
                and str(row["result_ref"] or "") == result
                and int(row["fencing_generation"]) == authority.fencing_generation
                and int(row["cancellation_epoch"]) == authority.cancellation_epoch
            ):
                return GovernedAgentWakeTransitionResult("idempotent", wake_record(row))
            if not claim_matches(row, authority, now):
                return GovernedAgentWakeTransitionResult("stale", wake_record(row))
            await conn.execute(
                """
                UPDATE governed_agent_wakes
                SET state = 'completed', result_ref = ?, claim_owner_id = NULL,
                    lease_expires_at_utc = NULL, uncertainty = 0, last_reason = NULL
                WHERE wake_id = ?
                """,
                (result, authority.wake_id),
            )
            return GovernedAgentWakeTransitionResult("applied", await required_wake(conn, authority.wake_id))

        return await self._execute(_op)

    async def release_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        reason: str,
        child_confirmed_stopped: bool,
        effect_uncertainty: bool,
    ) -> GovernedAgentWakeTransitionResult:
        now = utc_timestamp(now_utc)
        normalized_reason = required_text(reason, "E_AGENT_WAKE_RELEASE_REASON_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWakeTransitionResult:
            await conn.execute("BEGIN IMMEDIATE")
            row = await wake_row(conn, authority.wake_id)
            if row is not None and _same_release_transition(row, authority, normalized_reason):
                return GovernedAgentWakeTransitionResult("idempotent", wake_record(row))
            if row is None or not claim_identity_matches(row, authority):
                return GovernedAgentWakeTransitionResult("stale", optional_wake(row))
            recoverable = claim_matches(row, authority, now) and child_confirmed_stopped and not effect_uncertainty
            if recoverable:
                await conn.execute(
                    """
                    UPDATE governed_agent_wakes SET state = 'queued', claim_owner_id = NULL,
                        lease_expires_at_utc = NULL, uncertainty = 0, last_reason = ?
                    WHERE wake_id = ?
                    """,
                    (normalized_reason, authority.wake_id),
                )
            else:
                await conn.execute(
                    """
                    UPDATE governed_agent_wakes SET state = 'recovery_required',
                        uncertainty = 1, last_reason = ? WHERE wake_id = ?
                    """,
                    (normalized_reason, authority.wake_id),
                )
            return GovernedAgentWakeTransitionResult("applied", await required_wake(conn, authority.wake_id))

        return await self._execute(_op)

    async def cancel_wake(
        self,
        *,
        wake_id: str,
        expected_cancellation_epoch: int,
        cancellation_epoch: int,
        reason: str,
    ) -> GovernedAgentWakeTransitionResult:
        normalized_reason = required_text(reason, "E_AGENT_WAKE_CANCELLATION_REASON_REQUIRED")
        if cancellation_epoch <= expected_cancellation_epoch:
            raise ValueError("E_AGENT_WAKE_CANCELLATION_EPOCH_INVALID")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWakeTransitionResult:
            await conn.execute("BEGIN IMMEDIATE")
            row = await wake_row(conn, wake_id)
            if row is None:
                return GovernedAgentWakeTransitionResult("stale", None)
            if str(row["state"]) == "cancelled" and int(row["cancellation_epoch"]) == cancellation_epoch:
                return GovernedAgentWakeTransitionResult("idempotent", wake_record(row))
            if str(row["state"]) == "completed" or int(row["cancellation_epoch"]) != expected_cancellation_epoch:
                return GovernedAgentWakeTransitionResult("conflict", wake_record(row))
            uncertainty = 1 if str(row["state"]) == "claimed" else int(row["uncertainty"])
            await conn.execute(
                """
                UPDATE governed_agent_wakes SET state = 'cancelled', cancellation_epoch = ?,
                    uncertainty = ?, last_reason = ? WHERE wake_id = ?
                """,
                (cancellation_epoch, uncertainty, normalized_reason, wake_id),
            )
            return GovernedAgentWakeTransitionResult("applied", await required_wake(conn, wake_id))

        return await self._execute(_op)

    async def recover_expired_claim(
        self,
        *,
        wake_id: str,
        expected_fencing_generation: int,
        child_confirmed_stopped: bool,
        effect_uncertainty_cleared: bool,
        reason: str,
    ) -> GovernedAgentWakeTransitionResult:
        normalized_reason = required_text(reason, "E_AGENT_WAKE_RECOVERY_REASON_REQUIRED")

        async def _op(conn: aiosqlite.Connection) -> GovernedAgentWakeTransitionResult:
            await conn.execute("BEGIN IMMEDIATE")
            row = await wake_row(conn, wake_id)
            if row is None:
                return GovernedAgentWakeTransitionResult("stale", None)
            if (
                str(row["state"]) == "queued"
                and int(row["fencing_generation"]) == expected_fencing_generation
                and not bool(row["uncertainty"])
                and str(row["last_reason"] or "") == normalized_reason
            ):
                return GovernedAgentWakeTransitionResult("idempotent", wake_record(row))
            if str(row["state"]) != "recovery_required" or int(row["fencing_generation"]) != expected_fencing_generation:
                return GovernedAgentWakeTransitionResult("conflict", wake_record(row))
            if not child_confirmed_stopped or not effect_uncertainty_cleared:
                return GovernedAgentWakeTransitionResult("conflict", wake_record(row))
            await conn.execute(
                """
                UPDATE governed_agent_wakes SET state = 'queued', claim_owner_id = NULL,
                    lease_expires_at_utc = NULL, uncertainty = 0, last_reason = ? WHERE wake_id = ?
                """,
                (normalized_reason, wake_id),
            )
            return GovernedAgentWakeTransitionResult("applied", await required_wake(conn, wake_id))

        return await self._execute(_op)

    async def get_wake(self, *, wake_id: str) -> GovernedAgentWakeRecord | None:
        return await self._execute(lambda conn: get_wake(conn, wake_id))

    async def list_wakes(self, *, target_run_id: str | None = None) -> tuple[GovernedAgentWakeRecord, ...]:
        async def _op(conn: aiosqlite.Connection) -> tuple[GovernedAgentWakeRecord, ...]:
            if target_run_id is None:
                cursor = await conn.execute("SELECT * FROM governed_agent_wakes ORDER BY created_at_utc, wake_id")
            else:
                cursor = await conn.execute("SELECT * FROM governed_agent_wakes ORDER BY created_at_utc, wake_id")
            wakes = tuple(wake_record(row) for row in await cursor.fetchall())
            if target_run_id is None:
                return wakes
            return tuple(wake for wake in wakes if _wake_targets_run(wake, target_run_id))

        return await self._execute(_op)

    async def _execute(self, operation: Callable[[aiosqlite.Connection], Awaitable[ResultT]]) -> ResultT:
        async with self._lock, connect_sqlite_wal(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            if not self._initialized:
                await ensure_schema(conn)
                self._initialized = True
            result = await operation(conn)
            await conn.commit()
            return result


def _same_release_transition(
    row: aiosqlite.Row,
    authority: GovernedAgentWakeAuthority,
    reason: str,
) -> bool:
    return (
        str(row["state"]) in {"queued", "recovery_required"}
        and int(row["fencing_generation"]) == authority.fencing_generation
        and int(row["cancellation_epoch"]) == authority.cancellation_epoch
        and str(row["last_reason"] or "") == reason
    )


def _wake_targets_run(wake: GovernedAgentWakeRecord, run_id: str) -> bool:
    if wake.target_run_id == run_id:
        return True
    request = wake.payload.get("request")
    identity = request.get("identity") if isinstance(request, dict) else None
    return isinstance(identity, dict) and str(identity.get("run_id") or "") == run_id
