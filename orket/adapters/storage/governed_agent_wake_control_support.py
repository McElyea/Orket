from __future__ import annotations

import json
from typing import cast

import aiosqlite

from orket.adapters.storage.control_plane_operator_action_support import (
    insert_operator_action,
    operator_action_exists,
)
from orket.adapters.storage.governed_agent_wake_repository_support import (
    optional_text,
    optional_wake,
    payload_digest,
    payload_json,
    required_text,
    utc_timestamp,
    wake_row,
)
from orket.core.contracts import OperatorActionRecord
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeActionRecord,
    GovernedAgentWakeCancellationRequest,
    GovernedAgentWakeControlResult,
    GovernedAgentWakeRecoveryRequest,
    WakeControlKind,
    WakeState,
    WakeTransitionStatus,
)
from orket.core.domain import OperatorCommandClass, OperatorInputClass

side_effecting = True


async def apply_cancellation_transaction(
    conn: aiosqlite.Connection,
    request: GovernedAgentWakeCancellationRequest,
) -> GovernedAgentWakeControlResult:
    normalized = validated_cancellation(request)
    payload = _cancellation_payload(normalized)
    digest = payload_digest(payload_json(payload))
    await conn.execute("BEGIN IMMEDIATE")
    retained = await _retained_action(conn, action_id=normalized.action_id)
    if retained is not None:
        return _replayed_control_result(retained, digest, await wake_row(conn, normalized.wake_id))
    await _reject_canonical_action_collision(conn, normalized.action_id)
    row = await wake_row(conn, normalized.wake_id)
    status: WakeTransitionStatus
    if row is None:
        status = "stale"
    elif str(row["state"]) == "cancelled" and int(row["cancellation_epoch"]) == normalized.cancellation_epoch:
        status = "idempotent"
    elif str(row["state"]) == "completed" or int(row["cancellation_epoch"]) != normalized.expected_cancellation_epoch:
        status = "conflict"
    else:
        uncertainty = 1 if str(row["state"]) == "claimed" else int(row["uncertainty"])
        await conn.execute(
            """
            UPDATE governed_agent_wakes SET state = 'cancelled', cancellation_epoch = ?,
                uncertainty = ?, last_reason = ? WHERE wake_id = ?
            """,
            (normalized.cancellation_epoch, uncertainty, normalized.reason, normalized.wake_id),
        )
        status = "applied"
    resulting_row = await wake_row(conn, normalized.wake_id)
    action = await _insert_action(
        conn,
        action_id=normalized.action_id,
        wake_id=normalized.wake_id,
        action_kind="cancel",
        actor_ref=normalized.actor_ref,
        timestamp_utc=normalized.timestamp_utc,
        request_json=payload_json(payload),
        request_digest=digest,
        status=status,
        wake=resulting_row,
    )
    await _insert_canonical_operator_action(
        conn,
        request=normalized,
        request_digest=digest,
        status=status,
    )
    return GovernedAgentWakeControlResult(status, optional_wake(resulting_row), action)


async def apply_recovery_transaction(
    conn: aiosqlite.Connection,
    request: GovernedAgentWakeRecoveryRequest,
) -> GovernedAgentWakeControlResult:
    normalized = validated_recovery(request)
    payload = _recovery_payload(normalized)
    digest = payload_digest(payload_json(payload))
    await conn.execute("BEGIN IMMEDIATE")
    retained = await _retained_action(conn, action_id=normalized.action_id)
    if retained is not None:
        return _replayed_control_result(retained, digest, await wake_row(conn, normalized.wake_id))
    await _reject_canonical_action_collision(conn, normalized.action_id)
    row = await wake_row(conn, normalized.wake_id)
    status = await _apply_recovery_transition(conn, normalized, row)
    resulting_row = await wake_row(conn, normalized.wake_id)
    action = await _insert_action(
        conn,
        action_id=normalized.action_id,
        wake_id=normalized.wake_id,
        action_kind="recover",
        actor_ref=normalized.actor_ref,
        timestamp_utc=normalized.timestamp_utc,
        request_json=payload_json(payload),
        request_digest=digest,
        status=status,
        wake=resulting_row,
    )
    await _insert_canonical_operator_action(
        conn,
        request=normalized,
        request_digest=digest,
        status=status,
    )
    return GovernedAgentWakeControlResult(status, optional_wake(resulting_row), action)


async def list_action_records(
    conn: aiosqlite.Connection,
    *,
    wake_id: str,
) -> tuple[GovernedAgentWakeActionRecord, ...]:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_wake_actions WHERE wake_id = ? ORDER BY timestamp_utc, action_id",
        (required_text(wake_id, "E_AGENT_WAKE_ID_REQUIRED"),),
    )
    return tuple(action_record(row) for row in await cursor.fetchall())


def validated_cancellation(
    request: GovernedAgentWakeCancellationRequest,
) -> GovernedAgentWakeCancellationRequest:
    if request.expected_cancellation_epoch < 0 or request.cancellation_epoch <= request.expected_cancellation_epoch:
        raise ValueError("E_AGENT_WAKE_CANCELLATION_EPOCH_INVALID")
    return GovernedAgentWakeCancellationRequest(
        action_id=required_text(request.action_id, "E_AGENT_WAKE_ACTION_ID_REQUIRED"),
        wake_id=required_text(request.wake_id, "E_AGENT_WAKE_ID_REQUIRED"),
        actor_ref=required_text(request.actor_ref, "E_AGENT_WAKE_ACTOR_REQUIRED"),
        timestamp_utc=utc_timestamp(request.timestamp_utc),
        reason=required_text(request.reason, "E_AGENT_WAKE_CANCELLATION_REASON_REQUIRED"),
        expected_cancellation_epoch=request.expected_cancellation_epoch,
        cancellation_epoch=request.cancellation_epoch,
    )


def validated_recovery(request: GovernedAgentWakeRecoveryRequest) -> GovernedAgentWakeRecoveryRequest:
    if request.expected_fencing_generation < 0:
        raise ValueError("E_AGENT_WAKE_RECOVERY_FENCE_INVALID")
    if request.resolution not in {"requeue", "confirm_cancelled"}:
        raise ValueError("E_AGENT_WAKE_RECOVERY_RESOLUTION_INVALID")
    evidence_refs = tuple(required_text(item, "E_AGENT_WAKE_RECOVERY_EVIDENCE_REQUIRED") for item in request.evidence_refs)
    if not evidence_refs:
        raise ValueError("E_AGENT_WAKE_RECOVERY_EVIDENCE_REQUIRED")
    return GovernedAgentWakeRecoveryRequest(
        action_id=required_text(request.action_id, "E_AGENT_WAKE_ACTION_ID_REQUIRED"),
        wake_id=required_text(request.wake_id, "E_AGENT_WAKE_ID_REQUIRED"),
        actor_ref=required_text(request.actor_ref, "E_AGENT_WAKE_ACTOR_REQUIRED"),
        timestamp_utc=utc_timestamp(request.timestamp_utc),
        reason=required_text(request.reason, "E_AGENT_WAKE_RECOVERY_REASON_REQUIRED"),
        expected_fencing_generation=request.expected_fencing_generation,
        resolution=request.resolution,
        child_confirmed_stopped=bool(request.child_confirmed_stopped),
        effect_uncertainty_cleared=bool(request.effect_uncertainty_cleared),
        evidence_refs=evidence_refs,
    )


async def _apply_recovery_transition(
    conn: aiosqlite.Connection,
    request: GovernedAgentWakeRecoveryRequest,
    row: aiosqlite.Row | None,
) -> WakeTransitionStatus:
    if row is None:
        return "stale"
    if int(row["fencing_generation"]) != request.expected_fencing_generation:
        return "conflict"
    if not request.child_confirmed_stopped or not request.effect_uncertainty_cleared:
        return "conflict"
    if _recovery_already_applied(row, request):
        return "idempotent"
    eligible = (
        request.resolution == "requeue" and str(row["state"]) == "recovery_required"
    ) or (
        request.resolution == "confirm_cancelled"
        and str(row["state"]) == "cancelled"
        and bool(row["uncertainty"])
    )
    if not eligible:
        return "conflict"
    target_state = "queued" if request.resolution == "requeue" else "cancelled"
    await conn.execute(
        """
        UPDATE governed_agent_wakes SET state = ?, claim_owner_id = NULL,
            lease_expires_at_utc = NULL, uncertainty = 0, last_reason = ?
        WHERE wake_id = ?
        """,
        (target_state, request.reason, request.wake_id),
    )
    return "applied"


def _recovery_already_applied(row: aiosqlite.Row, request: GovernedAgentWakeRecoveryRequest) -> bool:
    target_state = "queued" if request.resolution == "requeue" else "cancelled"
    return (
        str(row["state"]) == target_state
        and not bool(row["uncertainty"])
        and str(row["last_reason"] or "") == request.reason
    )


async def _retained_action(conn: aiosqlite.Connection, *, action_id: str) -> GovernedAgentWakeActionRecord | None:
    cursor = await conn.execute(
        "SELECT * FROM governed_agent_wake_actions WHERE action_id = ?",
        (action_id,),
    )
    row = await cursor.fetchone()
    return None if row is None else action_record(row)


def _replayed_control_result(
    action: GovernedAgentWakeActionRecord,
    request_digest: str,
    wake_row_value: aiosqlite.Row | None,
) -> GovernedAgentWakeControlResult:
    status: WakeTransitionStatus = "idempotent" if action.request_digest == request_digest else "conflict"
    return GovernedAgentWakeControlResult(status, optional_wake(wake_row_value), action)


async def _insert_action(
    conn: aiosqlite.Connection,
    *,
    action_id: str,
    wake_id: str,
    action_kind: WakeControlKind,
    actor_ref: str,
    timestamp_utc: str,
    request_json: str,
    request_digest: str,
    status: WakeTransitionStatus,
    wake: aiosqlite.Row | None,
) -> GovernedAgentWakeActionRecord:
    await conn.execute(
        """
        INSERT INTO governed_agent_wake_actions (
            action_id, wake_id, action_kind, actor_ref, timestamp_utc,
            request_json, request_digest, status, resulting_state,
            resulting_fencing_generation, resulting_cancellation_epoch,
            resulting_uncertainty
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id, wake_id, action_kind, actor_ref, timestamp_utc,
            request_json, request_digest, status,
            None if wake is None else str(wake["state"]),
            None if wake is None else int(wake["fencing_generation"]),
            None if wake is None else int(wake["cancellation_epoch"]),
            None if wake is None else int(wake["uncertainty"]),
        ),
    )
    retained = await _retained_action(conn, action_id=action_id)
    if retained is None:
        raise RuntimeError("E_AGENT_WAKE_ACTION_PUBLICATION_MISSING")
    return retained


async def _reject_canonical_action_collision(conn: aiosqlite.Connection, action_id: str) -> None:
    if await operator_action_exists(conn, action_id=action_id):
        raise ValueError("E_AGENT_WAKE_ACTION_ID_CONFLICT")


async def _insert_canonical_operator_action(
    conn: aiosqlite.Connection,
    *,
    request: GovernedAgentWakeCancellationRequest | GovernedAgentWakeRecoveryRequest,
    request_digest: str,
    status: WakeTransitionStatus,
) -> None:
    receipt_ref = f"governed-agent-wake-action:{request.action_id}"
    if isinstance(request, GovernedAgentWakeCancellationRequest):
        control_kind = "cancel"
        precondition_basis_ref = f"wake-cancellation-epoch:{request.expected_cancellation_epoch}"
        command_class = OperatorCommandClass.RELEASE_OR_REVOKE_LEASE
        evidence_refs: tuple[str, ...] = ()
    else:
        control_kind = "recover"
        precondition_basis_ref = f"wake-fencing-generation:{request.expected_fencing_generation}"
        command_class = OperatorCommandClass.FORCE_RECONCILE
        evidence_refs = request.evidence_refs
    record = OperatorActionRecord(
        action_id=request.action_id,
        actor_ref=request.actor_ref,
        input_class=OperatorInputClass.COMMAND,
        target_ref=request.wake_id,
        timestamp=request.timestamp_utc,
        precondition_basis_ref=precondition_basis_ref,
        result=status,
        command_class=command_class,
        attestation_payload={
            "wake_control_kind": control_kind,
            "wake_action_request_digest": request_digest,
            "wake_action_status": status,
        },
        affected_transition_refs=[receipt_ref],
        affected_resource_refs=[request.wake_id],
        receipt_refs=[receipt_ref, *evidence_refs],
    )
    await insert_operator_action(conn, record=record)


def action_record(row: aiosqlite.Row) -> GovernedAgentWakeActionRecord:
    return GovernedAgentWakeActionRecord(
        action_id=str(row["action_id"]),
        wake_id=str(row["wake_id"]),
        action_kind=cast(WakeControlKind, str(row["action_kind"])),
        actor_ref=str(row["actor_ref"]),
        timestamp_utc=str(row["timestamp_utc"]),
        request=dict(json.loads(str(row["request_json"]))),
        request_digest=str(row["request_digest"]),
        status=cast(WakeTransitionStatus, str(row["status"])),
        resulting_state=cast(WakeState | None, optional_text(row["resulting_state"])),
        resulting_fencing_generation=(
            None if row["resulting_fencing_generation"] is None else int(row["resulting_fencing_generation"])
        ),
        resulting_cancellation_epoch=(
            None if row["resulting_cancellation_epoch"] is None else int(row["resulting_cancellation_epoch"])
        ),
        resulting_uncertainty=(None if row["resulting_uncertainty"] is None else bool(row["resulting_uncertainty"])),
    )


def _cancellation_payload(request: GovernedAgentWakeCancellationRequest) -> dict[str, object]:
    return {
        "action_kind": "cancel",
        "action_id": request.action_id,
        "wake_id": request.wake_id,
        "actor_ref": request.actor_ref,
        "timestamp_utc": request.timestamp_utc,
        "reason": request.reason,
        "expected_cancellation_epoch": request.expected_cancellation_epoch,
        "cancellation_epoch": request.cancellation_epoch,
    }


def _recovery_payload(request: GovernedAgentWakeRecoveryRequest) -> dict[str, object]:
    return {
        "action_kind": "recover",
        "action_id": request.action_id,
        "wake_id": request.wake_id,
        "actor_ref": request.actor_ref,
        "timestamp_utc": request.timestamp_utc,
        "reason": request.reason,
        "expected_fencing_generation": request.expected_fencing_generation,
        "resolution": request.resolution,
        "child_confirmed_stopped": request.child_confirmed_stopped,
        "effect_uncertainty_cleared": request.effect_uncertainty_cleared,
        "evidence_refs": list(request.evidence_refs),
    }
