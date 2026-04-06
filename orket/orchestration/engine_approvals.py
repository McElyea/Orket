from __future__ import annotations

import os
from typing import Any

from orket.application.services.governed_turn_tool_approval_continuation_service import (
    GovernedTurnToolApprovalContinuationService,
)
from orket.application.services.pending_gate_control_plane_operator_service import (
    PendingGateControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.kernel.v1.nervous_system_runtime_extensions import (
    decide_approval_v1,
    get_approval_v1,
    list_approvals_v1,
)
from orket.orchestration.approval_control_plane_read_model import (
    final_truth_summary,
    operator_action_summary,
    reservation_summary,
    target_checkpoint_summary,
    target_effect_journal_summary,
    target_resource_summary,
    target_run_summary,
    target_step_summary,
)


class ApprovalProjectionConflictError(RuntimeError):
    """Raised when the Packet 1 approval projection cannot be shaped truthfully."""


_PACKET1_APPROVAL_STATUSES = {"PENDING", "APPROVED", "DENIED"}


def _api_approval_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "pending": "PENDING",
        "approved": "APPROVED",
        "denied": "DENIED",
        "approved_with_edits": "APPROVED_WITH_EDITS",
        "expired": "EXPIRED",
    }
    return mapping.get(normalized, "PENDING")


def _normalize_packet1_status_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value or "").strip().upper()
    if normalized not in _PACKET1_APPROVAL_STATUSES:
        raise ValueError("status must be one of PENDING, APPROVED, DENIED")
    return normalized


def _repo_approval_status(value: str) -> str:
    mapping = {
        "PENDING": "pending",
        "APPROVED": "approved",
        "DENIED": "denied",
        "APPROVED_WITH_EDITS": "approved_with_edits",
        "EXPIRED": "expired",
    }
    normalized = str(value or "").strip().upper()
    if normalized not in mapping:
        raise ValueError("status must be one of PENDING, APPROVED, DENIED, APPROVED_WITH_EDITS, EXPIRED")
    return mapping[normalized]


def _normalize_approval_row(row: dict[str, Any]) -> dict[str, Any]:
    approval_id = str(row.get("request_id") or "").strip()
    return {
        "approval_id": approval_id,
        "request_id": approval_id,
        "session_id": str(row.get("session_id") or ""),
        "issue_id": str(row.get("issue_id") or ""),
        "seat_name": str(row.get("seat_name") or ""),
        "gate_mode": str(row.get("gate_mode") or ""),
        "request_type": str(row.get("request_type") or ""),
        "reason": str(row.get("reason") or ""),
        "payload": dict(row.get("payload_json") or {}),
        "status": _api_approval_status(row.get("status")),
        "resolution": dict(row.get("resolution_json") or {}),
        "created_at": str(row.get("created_at") or ""),
        "updated_at": str(row.get("updated_at") or ""),
        "resolved_at": str(row.get("resolved_at") or ""),
    }


def _nervous_system_enabled() -> bool:
    raw = str(os.environ.get("ORKET_ENABLE_NERVOUS_SYSTEM") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _approval_reservation_publisher(engine: Any) -> ToolApprovalControlPlaneReservationService | None:
    publication = getattr(engine, "control_plane_publication", None)
    publisher = getattr(engine, "tool_approval_control_plane_reservation", None)
    if (
        isinstance(publisher, ToolApprovalControlPlaneReservationService)
        and getattr(publisher, "publication", None) is publication
    ):
        return publisher
    if publication is None:
        return None
    publisher = ToolApprovalControlPlaneReservationService(publication=publication)
    engine.tool_approval_control_plane_reservation = publisher
    return publisher


def _tool_approval_operator_publisher(engine: Any) -> ToolApprovalControlPlaneOperatorService | None:
    publication = getattr(engine, "control_plane_publication", None)
    execution_repository = getattr(engine, "control_plane_execution_repository", None)
    publisher = getattr(engine, "tool_approval_control_plane_operator", None)
    if (
        isinstance(publisher, ToolApprovalControlPlaneOperatorService)
        and getattr(publisher, "publication", None) is publication
        and getattr(publisher, "execution_repository", None) is execution_repository
    ):
        return publisher
    if publication is None:
        return None
    publisher = ToolApprovalControlPlaneOperatorService(
        publication=publication,
        execution_repository=execution_repository,
    )
    engine.tool_approval_control_plane_operator = publisher
    return publisher


def _pending_gate_operator_publisher(engine: Any) -> PendingGateControlPlaneOperatorService | None:
    publication = getattr(engine, "control_plane_publication", None)
    publisher = getattr(engine, "pending_gate_control_plane_operator", None)
    if (
        isinstance(publisher, PendingGateControlPlaneOperatorService)
        and getattr(publisher, "publication", None) is publication
    ):
        return publisher
    if publication is None:
        return None
    publisher = PendingGateControlPlaneOperatorService(publication=publication)
    engine.pending_gate_control_plane_operator = publisher
    return publisher


def _governed_turn_tool_approval_continuation_service(
    engine: Any,
) -> GovernedTurnToolApprovalContinuationService | None:
    publication = getattr(engine, "control_plane_publication", None)
    execution_repository = getattr(engine, "control_plane_execution_repository", None)
    service = getattr(engine, "governed_turn_tool_approval_continuation", None)
    if (
        isinstance(service, GovernedTurnToolApprovalContinuationService)
        and getattr(service, "publication", None) is publication
        and getattr(service, "execution_repository", None) is execution_repository
    ):
        return service
    if publication is None or execution_repository is None:
        return None
    service = GovernedTurnToolApprovalContinuationService(
        execution_repository=execution_repository,
        publication=publication,
    )
    engine.governed_turn_tool_approval_continuation = service
    return service


async def list_approvals(
    engine: Any,
    *,
    session_id: str | None = None,
    status: str | None = None,
    request_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    normalized_status = _normalize_packet1_status_filter(status)
    if _nervous_system_enabled():
        items = list_approvals_v1(
            status=normalized_status,
            session_id=session_id,
            request_id=request_id,
            limit=limit,
        )
        return [await _enrich_approval_row(engine, item) for item in items]

    repo_status = None
    if normalized_status:
        repo_status = _repo_approval_status(normalized_status)
    rows = await engine.pending_gates.list_requests(
        session_id=session_id,
        status=repo_status,
        limit=max(1, int(limit)),
    )
    items = [_normalize_approval_row(row) for row in rows]
    normalized_request_id = str(request_id or "").strip()
    if normalized_request_id:
        items = [item for item in items if item["approval_id"] == normalized_request_id]
    return [await _enrich_approval_row(engine, item) for item in items]


async def get_approval(engine: Any, approval_id: str) -> dict[str, Any] | None:
    if _nervous_system_enabled():
        approval = get_approval_v1(approval_id)
        if approval is None:
            return None
        return await _enrich_approval_row(engine, approval)

    normalized_id = str(approval_id or "").strip()
    if not normalized_id:
        return None
    rows = await engine.pending_gates.list_requests(limit=1000)
    for row in rows:
        if str(row.get("request_id") or "").strip() == normalized_id:
            return await _enrich_approval_row(engine, _normalize_approval_row(row))
    return None


async def decide_approval(
    engine: Any,
    *,
    approval_id: str,
    decision: str,
    edited_proposal: dict[str, Any] | None = None,
    notes: str | None = None,
    operator_actor_ref: str | None = None,
) -> dict[str, Any]:
    if _nervous_system_enabled():
        existing = await get_approval(engine, approval_id)
        result = decide_approval_v1(
            approval_id=approval_id,
            decision=decision,
            edited_proposal=edited_proposal,
            notes=notes,
        )
        await _publish_resolution_control_plane_side_effects(
            engine=engine,
            previous=existing,
            result=result,
            operator_actor_ref=operator_actor_ref,
        )
        approval = result.get("approval")
        if isinstance(approval, dict):
            result["approval"] = await _enrich_approval_row(engine, approval)
        return result

    existing = await get_approval(engine, approval_id)
    if not existing:
        raise ValueError("approval not found")

    decision_token = str(decision or "").strip().lower()
    decision_map = {
        "approve": "APPROVED",
        "deny": "DENIED",
    }
    target_status = decision_map.get(decision_token)
    if not target_status:
        raise ValueError("decision must be one of: approve, deny")

    resolution: dict[str, Any] = {"decision": decision_token}
    if edited_proposal is not None:
        resolution["edited_proposal"] = edited_proposal
    note_text = str(notes or "").strip()
    if note_text:
        resolution["notes"] = note_text

    current_status = existing["status"]
    current_resolution = dict(existing.get("resolution") or {})
    if current_status != "PENDING":
        if current_status == target_status and current_resolution == resolution:
            return {"status": "idempotent", "approval": existing}
        raise RuntimeError("approval already resolved with a conflicting decision")

    await engine.pending_gates.resolve_request(
        request_id=approval_id,
        status=_repo_approval_status(target_status),
        resolution=resolution,
    )
    updated = await get_approval(engine, approval_id)
    if not updated:
        raise RuntimeError("approval resolution persisted but lookup failed")
    result = {"status": "resolved", "approval": updated}
    await _publish_resolution_control_plane_side_effects(
        engine=engine,
        previous=existing,
        result=result,
        operator_actor_ref=operator_actor_ref,
    )
    result["approval"] = await _enrich_approval_row(engine, updated)
    return result


async def _publish_resolution_control_plane_side_effects(
    *,
    engine: Any,
    previous: dict[str, Any] | None,
    result: dict[str, Any],
    operator_actor_ref: str | None,
) -> None:
    if str(result.get("status") or "").strip().lower() != "resolved":
        return
    approval = result.get("approval")
    if not isinstance(approval, dict):
        return
    status = str(approval.get("status") or "").strip().upper()
    if status not in {"APPROVED", "DENIED"}:
        return
    reservation_publisher = _approval_reservation_publisher(engine)
    if reservation_publisher is not None:
        await reservation_publisher.publish_resolved_pending_gate_hold(resolved_approval=approval)
    if operator_actor_ref:
        tool_publisher = _tool_approval_operator_publisher(engine)
        if tool_publisher is not None and tool_publisher.supports_resolution(approval):
            await tool_publisher.publish_resolution_operator_action(
                actor_ref=operator_actor_ref,
                previous_approval=previous,
                resolved_approval=approval,
            )
        else:
            pending_gate_publisher = _pending_gate_operator_publisher(engine)
            if pending_gate_publisher is not None and pending_gate_publisher.supports_resolution(approval):
                await pending_gate_publisher.publish_resolution_operator_action(
                    actor_ref=operator_actor_ref,
                    previous_approval=previous,
                    resolved_approval=approval,
                )
    continuation_service = _governed_turn_tool_approval_continuation_service(engine)
    if continuation_service is None or not continuation_service.supports_resolution(approval):
        return
    await continuation_service.continue_or_stop(
        engine=engine,
        resolved_approval=approval,
    )


async def _enrich_approval_row(engine: Any, approval: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(approval)
    enriched["control_plane_target_ref"] = None
    enriched["control_plane_target_run"] = None
    enriched["control_plane_target_step"] = None
    enriched["control_plane_target_checkpoint"] = None
    enriched["control_plane_target_effect_journal"] = None
    enriched["control_plane_target_operator_action"] = None
    enriched["control_plane_target_resource"] = None
    enriched["control_plane_target_reservation"] = None
    enriched["control_plane_target_final_truth"] = None
    approval_id = str(enriched.get("approval_id") or "").strip()
    if not approval_id:
        enriched["control_plane_operator_action"] = None
        return enriched
    status = _require_packet1_approval_status(approval_id=approval_id, status=enriched.get("status"))

    repository = getattr(engine, "control_plane_repository", None)
    if repository is None:
        enriched["control_plane_operator_action"] = None
        return enriched

    approval_target_ref = ToolApprovalControlPlaneOperatorService.target_ref(approval_id)
    reservation = await repository.get_latest_reservation_record(
        reservation_id=ToolApprovalControlPlaneReservationService.reservation_id(approval_id)
    )
    enriched["control_plane_target_ref"] = _approval_target_ref(
        enriched,
        approval_id=approval_id,
        approval_target_ref=approval_target_ref,
        reservation=reservation,
    )
    actions = await repository.list_operator_actions(target_ref=approval_target_ref)
    if not actions:
        enriched["control_plane_operator_action"] = None
    else:
        enriched["control_plane_operator_action"] = operator_action_summary(actions[-1])
        _validate_operator_action_projection(
            approval_id=approval_id,
            status=status,
            field_name="control_plane_operator_action",
            action=enriched["control_plane_operator_action"],
        )

    target_ref = enriched["control_plane_target_ref"]
    if target_ref:
        execution_repository = getattr(engine, "control_plane_execution_repository", None)
        if execution_repository is not None:
            target_run = await target_run_summary(execution_repository=execution_repository, run_id=target_ref)
            if target_run is not None:
                enriched["control_plane_target_run"] = target_run
                enriched["control_plane_target_resource"] = await target_resource_summary(
                    repository=repository,
                    execution_repository=execution_repository,
                    run_id=target_ref,
                )
                enriched["control_plane_target_step"] = await target_step_summary(
                    execution_repository=execution_repository,
                    attempt_id=target_run["current_attempt_id"],
                )
                enriched["control_plane_target_checkpoint"] = await target_checkpoint_summary(
                    repository=repository,
                    attempt_id=target_run["current_attempt_id"],
                )
        enriched["control_plane_target_effect_journal"] = await target_effect_journal_summary(
            repository=repository,
            run_id=target_ref,
        )
        target_actions = await repository.list_operator_actions(target_ref=target_ref)
        if target_actions:
            enriched["control_plane_target_operator_action"] = operator_action_summary(target_actions[-1])
            _validate_operator_action_projection(
                approval_id=approval_id,
                status=status,
                field_name="control_plane_target_operator_action",
                action=enriched["control_plane_target_operator_action"],
            )
        target_reservation = await repository.get_latest_reservation_record_for_holder_ref(holder_ref=target_ref)
        if target_reservation is not None:
            enriched["control_plane_target_reservation"] = reservation_summary(target_reservation)
        target_final_truth = await repository.get_final_truth(run_id=target_ref)
        if target_final_truth is not None:
            enriched["control_plane_target_final_truth"] = final_truth_summary(target_final_truth)

    if reservation is None:
        enriched["control_plane_reservation"] = None
        return enriched
    enriched["control_plane_reservation"] = reservation_summary(reservation)
    return enriched


def _approval_target_ref(
    approval: dict[str, Any],
    *,
    approval_id: str,
    approval_target_ref: str,
    reservation: Any | None,
) -> str | None:
    payload = approval.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    payload_target_ref = str(payload.get("control_plane_target_ref") or "").strip()
    if reservation is None:
        return payload_target_ref or None
    holder_ref = str(getattr(reservation, "holder_ref", "") or "").strip()
    reservation_target_ref = None if not holder_ref or holder_ref == approval_target_ref else holder_ref
    if payload_target_ref and reservation_target_ref and payload_target_ref != reservation_target_ref:
        raise ApprovalProjectionConflictError(
            f"approval '{approval_id}' target projection drift between payload and reservation holder"
        )
    return payload_target_ref or reservation_target_ref


def _require_packet1_approval_status(*, approval_id: str, status: Any) -> str:
    normalized = str(status or "").strip().upper()
    if normalized not in _PACKET1_APPROVAL_STATUSES:
        raise ApprovalProjectionConflictError(
            f"approval '{approval_id}' has unsupported Packet 1 status '{normalized or '<empty>'}'"
        )
    return normalized


def _validate_operator_action_projection(
    *,
    approval_id: str,
    status: str,
    field_name: str,
    action: dict[str, Any] | None,
) -> None:
    if action is None:
        return
    if status == "PENDING":
        raise ApprovalProjectionConflictError(
            f"approval '{approval_id}' has conflicting {field_name} while still pending"
        )
    expected_result = "approved" if status == "APPROVED" else "denied"
    actual_result = str(action.get("result") or "").strip().lower()
    if actual_result != expected_result:
        raise ApprovalProjectionConflictError(
            f"approval '{approval_id}' has conflicting {field_name} result '{actual_result or '<empty>'}'"
        )

__all__ = ["decide_approval", "get_approval", "list_approvals"]
