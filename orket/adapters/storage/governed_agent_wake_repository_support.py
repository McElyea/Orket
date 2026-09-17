from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import aiosqlite

from orket.adapters.storage.control_plane_operator_action_support import (
    ensure_operator_action_schema,
)
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeAuthority,
    GovernedAgentWakeClaimResult,
    GovernedAgentWakeEnqueueResult,
    GovernedAgentWakeRecord,
    GovernedAgentWakeRequest,
    WakeSource,
    WakeState,
    WakeTargetKind,
)


async def enqueue_transaction(
    conn: aiosqlite.Connection,
    request: GovernedAgentWakeRequest,
    *,
    begin: bool = True,
    admit_scheduled: bool = False,
    admit_webhook: bool = False,
) -> GovernedAgentWakeEnqueueResult:
    normalized = validated_request(
        request,
        admit_scheduled=admit_scheduled,
        admit_webhook=admit_webhook,
    )
    serialized_payload = payload_json(normalized.payload)
    digest = payload_digest(serialized_payload)
    if begin:
        await conn.execute("BEGIN IMMEDIATE")
    same_identity = await wake_row(conn, normalized.wake_id)
    if same_identity is not None:
        wake = wake_record(same_identity)
        return GovernedAgentWakeEnqueueResult(
            "idempotent" if same_request(wake, normalized, digest) else "conflict",
            wake,
        )
    existing = await deduplication_row(conn, normalized.source, normalized.deduplication_key)
    if existing is not None:
        wake = wake_record(existing)
        return GovernedAgentWakeEnqueueResult(
            "idempotent" if same_request(wake, normalized, digest) else "conflict",
            wake,
        )
    await conn.execute(
        """
        INSERT INTO governed_agent_wakes (
            wake_id, source, target_kind, target_run_id, workload_id, occurrence_id,
            deduplication_key, payload_json, payload_digest, created_at_utc, state
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued')
        """,
        (
            normalized.wake_id,
            normalized.source,
            normalized.target_kind,
            normalized.target_run_id,
            normalized.workload_id,
            normalized.occurrence_id,
            normalized.deduplication_key,
            serialized_payload,
            digest,
            normalized.created_at_utc,
        ),
    )
    return GovernedAgentWakeEnqueueResult("enqueued", await required_wake(conn, normalized.wake_id))


async def claim_next_transaction(
    conn: aiosqlite.Connection,
    *,
    owner: str,
    now: str,
    lease_expiry: str,
    max_active_claims: int,
) -> GovernedAgentWakeClaimResult:
    await conn.execute("BEGIN IMMEDIATE")
    await conn.execute(
        """
        UPDATE governed_agent_wakes
        SET state = 'recovery_required', uncertainty = 1,
            last_reason = 'expired_claim_requires_recovery'
        WHERE state = 'claimed' AND lease_expires_at_utc <= ?
        """,
        (now,),
    )
    retained = await _active_owner_claim(conn, owner=owner, now=now)
    if retained is not None:
        authority = GovernedAgentWakeAuthority(
            wake_id=retained.wake_id,
            owner_id=owner,
            fencing_generation=retained.fencing_generation,
            cancellation_epoch=retained.cancellation_epoch,
            lease_expires_at_utc=str(retained.lease_expires_at_utc),
        )
        return GovernedAgentWakeClaimResult("idempotent", retained, authority)
    cursor = await conn.execute(
        """
        SELECT * FROM governed_agent_wakes
        WHERE state = 'queued'
        ORDER BY created_at_utc, wake_id LIMIT 1
        """
    )
    row = await cursor.fetchone()
    if row is None:
        return GovernedAgentWakeClaimResult("empty", None, None)
    cursor = await conn.execute(
        "SELECT COUNT(*) AS count FROM governed_agent_wakes WHERE state = 'claimed' OR uncertainty = 1"
    )
    count_row = await cursor.fetchone()
    if count_row is None:
        raise RuntimeError("E_AGENT_WAKE_CAPACITY_COUNT_MISSING")
    if int(count_row["count"]) >= max_active_claims:
        return GovernedAgentWakeClaimResult("capacity", None, None)
    generation = int(row["fencing_generation"]) + 1
    updated = await conn.execute(
        """
        UPDATE governed_agent_wakes
        SET state = 'claimed', claim_owner_id = ?, lease_expires_at_utc = ?,
            fencing_generation = ?, uncertainty = 0, last_reason = NULL
        WHERE wake_id = ? AND state = 'queued' AND fencing_generation = ?
        """,
        (owner, lease_expiry, generation, str(row["wake_id"]), int(row["fencing_generation"])),
    )
    if updated.rowcount != 1:
        return GovernedAgentWakeClaimResult("empty", None, None)
    wake = await required_wake(conn, str(row["wake_id"]))
    authority = GovernedAgentWakeAuthority(
        wake_id=wake.wake_id,
        owner_id=owner,
        fencing_generation=generation,
        cancellation_epoch=wake.cancellation_epoch,
        lease_expires_at_utc=lease_expiry,
    )
    return GovernedAgentWakeClaimResult("claimed", wake, authority)


async def _active_owner_claim(
    conn: aiosqlite.Connection,
    *,
    owner: str,
    now: str,
) -> GovernedAgentWakeRecord | None:
    cursor = await conn.execute(
        """
        SELECT * FROM governed_agent_wakes
        WHERE state = 'claimed' AND claim_owner_id = ? AND lease_expires_at_utc > ?
        ORDER BY created_at_utc, wake_id LIMIT 1
        """,
        (owner, now),
    )
    return optional_wake(await cursor.fetchone())


async def ensure_schema(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS governed_agent_wakes (
            wake_id TEXT PRIMARY KEY, source TEXT NOT NULL, target_kind TEXT NOT NULL,
            target_run_id TEXT, workload_id TEXT, occurrence_id TEXT NOT NULL,
            deduplication_key TEXT NOT NULL, payload_json TEXT NOT NULL, payload_digest TEXT NOT NULL,
            created_at_utc TEXT NOT NULL, state TEXT NOT NULL, claim_owner_id TEXT,
            lease_expires_at_utc TEXT, fencing_generation INTEGER NOT NULL DEFAULT 0,
            cancellation_epoch INTEGER NOT NULL DEFAULT 0, uncertainty INTEGER NOT NULL DEFAULT 0,
            result_ref TEXT, last_reason TEXT, UNIQUE(source, deduplication_key)
        );
        CREATE INDEX IF NOT EXISTS idx_governed_agent_wakes_claim
        ON governed_agent_wakes(state, created_at_utc, wake_id);
        CREATE TABLE IF NOT EXISTS governed_agent_wake_actions (
            action_id TEXT PRIMARY KEY, wake_id TEXT NOT NULL, action_kind TEXT NOT NULL,
            actor_ref TEXT NOT NULL, timestamp_utc TEXT NOT NULL,
            request_json TEXT NOT NULL, request_digest TEXT NOT NULL,
            status TEXT NOT NULL, resulting_state TEXT,
            resulting_fencing_generation INTEGER, resulting_cancellation_epoch INTEGER,
            resulting_uncertainty INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_governed_agent_wake_actions_target
        ON governed_agent_wake_actions(wake_id, timestamp_utc, action_id);
        """
    )
    await ensure_operator_action_schema(conn)


def validated_request(
    request: GovernedAgentWakeRequest,
    *,
    admit_scheduled: bool = False,
    admit_webhook: bool = False,
) -> GovernedAgentWakeRequest:
    allowed_sources = {"manual", "api", "recovery"}
    if admit_scheduled:
        allowed_sources.add("scheduled")
    if admit_webhook:
        allowed_sources.add("webhook")
    if request.source not in allowed_sources:
        raise ValueError("E_AGENT_WAKE_SOURCE_NOT_ADMITTED")
    if request.target_kind not in {"existing_run", "new_run"}:
        raise ValueError("E_AGENT_WAKE_TARGET_KIND_INVALID")
    target_run_id = optional_text(request.target_run_id)
    workload_id = optional_text(request.workload_id)
    if request.target_kind == "existing_run" and (target_run_id is None or workload_id is not None):
        raise ValueError("E_AGENT_WAKE_EXISTING_RUN_TARGET_INVALID")
    if request.target_kind == "new_run" and (workload_id is None or target_run_id is not None):
        raise ValueError("E_AGENT_WAKE_NEW_RUN_TARGET_INVALID")
    if not isinstance(request.payload, Mapping):
        raise ValueError("E_AGENT_WAKE_PAYLOAD_OBJECT_REQUIRED")
    if request.source == "scheduled":
        trigger = request.payload.get("trigger")
        if not isinstance(trigger, Mapping) or trigger.get("schema_version") != "governed_agent_schedule_trigger.v1":
            raise ValueError("E_AGENT_SCHEDULE_TRIGGER_REQUIRED")
    if request.source == "webhook":
        trigger = request.payload.get("trigger")
        if not isinstance(trigger, Mapping) or trigger.get("schema_version") != "governed_agent_webhook_trigger.v1":
            raise ValueError("E_AGENT_WEBHOOK_TRIGGER_REQUIRED")
    return GovernedAgentWakeRequest(
        wake_id=required_text(request.wake_id, "E_AGENT_WAKE_ID_REQUIRED"),
        source=request.source,
        target_kind=request.target_kind,
        target_run_id=target_run_id,
        workload_id=workload_id,
        occurrence_id=required_text(request.occurrence_id, "E_AGENT_WAKE_OCCURRENCE_REQUIRED"),
        deduplication_key=required_text(
            request.deduplication_key,
            "E_AGENT_WAKE_DEDUPLICATION_KEY_REQUIRED",
        ),
        payload=dict(request.payload),
        created_at_utc=utc_timestamp(request.created_at_utc),
    )


def same_request(wake: GovernedAgentWakeRecord, request: GovernedAgentWakeRequest, digest: str) -> bool:
    return bool(
        wake.wake_id == request.wake_id
        and wake.source == request.source
        and wake.target_kind == request.target_kind
        and wake.target_run_id == request.target_run_id
        and wake.workload_id == request.workload_id
        and wake.occurrence_id == request.occurrence_id
        and wake.deduplication_key == request.deduplication_key
        and wake.payload_digest == digest
    )


def claim_matches(row: aiosqlite.Row, authority: GovernedAgentWakeAuthority, now: str) -> bool:
    return claim_identity_matches(row, authority) and str(row["lease_expires_at_utc"] or "") > now


def claim_identity_matches(row: aiosqlite.Row, authority: GovernedAgentWakeAuthority) -> bool:
    return (
        str(row["state"]) == "claimed"
        and str(row["claim_owner_id"] or "") == authority.owner_id
        and int(row["fencing_generation"]) == authority.fencing_generation
        and int(row["cancellation_epoch"]) == authority.cancellation_epoch
        and not bool(row["uncertainty"])
    )


async def deduplication_row(conn: aiosqlite.Connection, source: str, key: str) -> aiosqlite.Row | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_wakes WHERE source = ? AND deduplication_key = ?",
        (source, key),
    )
    return await cursor.fetchone()


async def wake_row(conn: aiosqlite.Connection, wake_id: str) -> aiosqlite.Row | None:
    cursor = await conn.execute("SELECT * FROM governed_agent_wakes WHERE wake_id = ?", (wake_id,))
    return await cursor.fetchone()


async def required_wake(conn: aiosqlite.Connection, wake_id: str) -> GovernedAgentWakeRecord:
    row = await wake_row(conn, wake_id)
    if row is None:
        raise ValueError("E_AGENT_WAKE_MISSING")
    return wake_record(row)


async def get_wake(conn: aiosqlite.Connection, wake_id: str) -> GovernedAgentWakeRecord | None:
    return optional_wake(await wake_row(conn, wake_id))


def optional_wake(row: aiosqlite.Row | None) -> GovernedAgentWakeRecord | None:
    return None if row is None else wake_record(row)


def wake_record(row: aiosqlite.Row) -> GovernedAgentWakeRecord:
    return GovernedAgentWakeRecord(
        wake_id=str(row["wake_id"]),
        source=cast(WakeSource, str(row["source"])),
        target_kind=cast(WakeTargetKind, str(row["target_kind"])),
        target_run_id=optional_text(row["target_run_id"]),
        workload_id=optional_text(row["workload_id"]),
        occurrence_id=str(row["occurrence_id"]),
        deduplication_key=str(row["deduplication_key"]),
        payload=dict(json.loads(str(row["payload_json"]))),
        payload_digest=str(row["payload_digest"]),
        created_at_utc=str(row["created_at_utc"]),
        state=cast(WakeState, str(row["state"])),
        claim_owner_id=optional_text(row["claim_owner_id"]),
        lease_expires_at_utc=optional_text(row["lease_expires_at_utc"]),
        fencing_generation=int(row["fencing_generation"]),
        cancellation_epoch=int(row["cancellation_epoch"]),
        uncertainty=bool(row["uncertainty"]),
        result_ref=optional_text(row["result_ref"]),
        last_reason=optional_text(row["last_reason"]),
    )


def payload_json(payload: Mapping[str, Any]) -> str:
    try:
        return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("E_AGENT_WAKE_PAYLOAD_NOT_SERIALIZABLE") from exc


def payload_digest(serialized_payload: str) -> str:
    return "sha256:" + hashlib.sha256(serialized_payload.encode("utf-8")).hexdigest()


def utc_timestamp(value: str) -> str:
    raw = required_text(value, "E_AGENT_WAKE_TIMESTAMP_REQUIRED")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("E_AGENT_WAKE_TIMESTAMP_INVALID") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("E_AGENT_WAKE_TIMESTAMP_NOT_UTC")
    return parsed.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def required_text(value: object, code: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(code)
    return normalized


def optional_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
