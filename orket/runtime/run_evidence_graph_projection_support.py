from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orket.application.services.control_plane_target_resource_refs import resource_id_for_supported_run
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    holder_ref_for_run as kernel_action_holder_ref_for_run,
)
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    lease_id_for_run as kernel_action_lease_id_for_run,
)
from orket.application.services.kernel_action_control_plane_resource_lifecycle import (
    reservation_id_for_run as kernel_action_reservation_id_for_run,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    lease_id_for_run as orchestrator_issue_lease_id_for_run,
)
from orket.application.services.orchestrator_issue_control_plane_support import (
    reservation_id_for_run as orchestrator_issue_reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    holder_ref_for_run as turn_tool_holder_ref_for_run,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run as turn_tool_lease_id_for_run,
)
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    reservation_id_for_run as turn_tool_reservation_id_for_run,
)
from orket.core.domain import RunState
from orket.runtime.run_evidence_graph import (
    RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS,
    build_blocked_run_evidence_graph_payload,
)

DEFAULT_VIEWS = list(RUN_EVIDENCE_GRAPH_DEFAULT_VIEWS)
TERMINAL_RUN_STATES = {
    RunState.COMPLETED,
    RunState.FAILED_TERMINAL,
    RunState.CANCELLED,
}


@dataclass(slots=True)
class PrimaryLineageContext:
    run: Any
    attempts: list[Any]
    attempts_by_id: dict[str, Any]
    steps_by_attempt: dict[str, list[Any]]
    steps_by_id: dict[str, Any]
    recovery_by_id: dict[str, Any]
    checkpoint_by_id: dict[str, Any]
    checkpoint_acceptance_by_id: dict[str, Any]
    effects: list[Any]
    reservation: Any | None
    lease: Any | None
    resource: Any | None
    final_truth: Any | None
    reconciliations: list[Any]
    linked_reconciliation_id: str
    operator_actions: list[Any]
    sources: dict[str, dict[str, Any]]


async def load_latest_reservation_record(*, record_repository: Any, run: Any) -> Any | None:
    reservation_id = ""
    holder_refs: list[str] = []
    if str(run.run_id).startswith("turn-tool-run:"):
        reservation_id = turn_tool_reservation_id_for_run(run_id=run.run_id)
        holder_refs = [run.run_id, turn_tool_holder_ref_for_run(run_id=run.run_id)]
    elif str(run.run_id).startswith("kernel-action-run:"):
        reservation_id = kernel_action_reservation_id_for_run(run_id=run.run_id)
        holder_refs = [run.run_id, kernel_action_holder_ref_for_run(run_id=run.run_id)]
    elif str(run.run_id).startswith(("orchestrator-issue-run:", "orchestrator-issue-scheduler-run:", "orchestrator-child-workload-run:")):
        reservation_id = orchestrator_issue_reservation_id_for_run(run_id=run.run_id)
    if reservation_id:
        canonical = await record_repository.get_latest_reservation_record(reservation_id=reservation_id)
        if canonical is not None:
            return canonical
    candidates: list[Any] = []
    for holder_ref in holder_refs:
        record = await record_repository.get_latest_reservation_record_for_holder_ref(holder_ref=holder_ref)
        if record is not None:
            candidates.append(record)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda record: (str(record.creation_timestamp), str(record.reservation_id), str(record.status.value)),
    )


async def load_latest_lease_record(*, record_repository: Any, run: Any) -> Any | None:
    lease_id = ""
    if str(run.run_id).startswith("turn-tool-run:"):
        lease_id = turn_tool_lease_id_for_run(run_id=run.run_id)
    elif str(run.run_id).startswith("kernel-action-run:"):
        lease_id = kernel_action_lease_id_for_run(run_id=run.run_id)
    elif str(run.run_id).startswith(("orchestrator-issue-run:", "orchestrator-issue-scheduler-run:", "orchestrator-child-workload-run:")):
        lease_id = orchestrator_issue_lease_id_for_run(run_id=run.run_id)
    if not lease_id:
        return None
    return await record_repository.get_latest_lease_record(lease_id=lease_id)


async def load_latest_resource_record(*, record_repository: Any, run: Any) -> Any | None:
    resource_id = resource_id_for_supported_run(run=run)
    if not resource_id:
        return None
    return await record_repository.get_latest_resource_record(resource_id=resource_id)


def blocked_payload(
    *,
    run_id: str,
    generation_timestamp: str,
    selected_views: list[str],
    sources: dict[str, dict[str, Any]],
    code: str,
    detail: str,
    source_id: str,
) -> dict[str, Any]:
    return build_blocked_run_evidence_graph_payload(
        run_id=run_id,
        generation_timestamp=generation_timestamp,
        selected_views=selected_views,
        source_summaries=list(sources.values()),
        issues=[issue(code=code, detail=detail, source_id=source_id)],
    )


def add_record_node(
    nodes: dict[str, dict[str, Any]],
    ref_to_node_id: dict[str, str],
    record: Any,
    *,
    family: str,
    record_id: str,
    record_ref: str,
    alternate_refs: list[str] | None = None,
) -> None:
    node_id = node_key(family, record_id)
    nodes[node_id] = {
        "id": node_id,
        "family": family,
        "label": record_id,
        "source_ids": [source_id(type(record).__name__, record_id)],
        "attributes": record.model_dump(mode="json"),
    }
    ref_to_node_id[record_ref] = node_id
    for alternate_ref in alternate_refs or []:
        if str(alternate_ref or "").strip():
            ref_to_node_id[str(alternate_ref)] = node_id


def add_edge(
    edges: dict[str, dict[str, Any]],
    family: str,
    source: str,
    target: str,
    source_refs: list[str],
    source_kind: str,
    target_kind: str,
) -> None:
    add_edge_with_source_ids(
        edges,
        family=family,
        source=source,
        target=target,
        source_ids=[source_id(source_kind, source_refs[0]), source_id(target_kind, source_refs[-1])],
    )


def add_edge_with_source_ids(
    edges: dict[str, dict[str, Any]],
    *,
    family: str,
    source: str,
    target: str,
    source_ids: list[str],
) -> None:
    edge_id = f"edge:{family}:{source}:{target}"
    edges[edge_id] = {
        "id": edge_id,
        "family": family,
        "source": source,
        "target": target,
        "source_ids": sorted({str(token).strip() for token in source_ids if str(token).strip()}),
    }


def record_kind_for_ref(ref: str, nodes: dict[str, dict[str, Any]], ref_to_node_id: dict[str, str]) -> str:
    node = nodes.get(ref_to_node_id[ref], {})
    return {
        "run": "RunRecord",
        "attempt": "AttemptRecord",
        "step": "StepRecord",
        "reservation": "ReservationRecord",
        "lease": "LeaseRecord",
        "resource": "ResourceRecord",
        "checkpoint": "CheckpointRecord",
        "checkpoint_acceptance": "CheckpointAcceptanceRecord",
        "effect": "EffectJournalEntryRecord",
        "recovery_decision": "RecoveryDecisionRecord",
        "reconciliation": "ReconciliationRecord",
        "operator_action": "OperatorActionRecord",
        "final_truth": "FinalTruthRecord",
    }.get(str(node.get("family") or ""), "RunRecord")


def put_source(sources: dict[str, dict[str, Any]], source: dict[str, Any]) -> None:
    sources[str(source["source_id"])] = source


def record_source_summary(*, record_kind: str, record_id: str) -> dict[str, Any]:
    return source_summary(
        source_id=source_id(record_kind, record_id),
        authority_level="primary",
        source_kind=record_kind,
        status="present",
        source_ref=record_id,
    )


def source_summary(
    *,
    source_id: str,
    authority_level: str,
    source_kind: str,
    status: str,
    source_ref: str,
    detail: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "source_id": source_id,
        "authority_level": authority_level,
        "source_kind": source_kind,
        "status": status,
        "source_ref": source_ref,
    }
    if detail:
        payload["detail"] = detail
    if attributes:
        payload["attributes"] = dict(attributes)
    return payload


def issue(*, code: str, detail: str, source_id: str | None = None) -> dict[str, Any]:
    payload = {"code": code, "detail": detail}
    if source_id:
        payload["source_id"] = source_id
    return payload


def source_id(record_kind: str, record_id: str) -> str:
    return f"source:{record_kind}:{record_id}"


def node_key(family: str, record_id: str) -> str:
    return f"{family}:{record_id}"


__all__ = [
    "DEFAULT_VIEWS",
    "PrimaryLineageContext",
    "TERMINAL_RUN_STATES",
    "add_edge",
    "add_edge_with_source_ids",
    "add_record_node",
    "blocked_payload",
    "issue",
    "load_latest_lease_record",
    "load_latest_reservation_record",
    "load_latest_resource_record",
    "node_key",
    "put_source",
    "record_kind_for_ref",
    "record_source_summary",
    "source_id",
    "source_summary",
]
