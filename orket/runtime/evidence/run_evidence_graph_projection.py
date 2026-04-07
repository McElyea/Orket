from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from orket.runtime.run_evidence_graph import (
    build_blocked_run_evidence_graph_payload,
    build_run_evidence_graph_payload,
)
from orket.runtime.run_evidence_graph_projection_collect import collect_primary_lineage_context
from orket.runtime.run_evidence_graph_projection_supplemental import load_supplemental_projection
from orket.runtime.run_evidence_graph_projection_support import (
    DEFAULT_VIEWS,
    PrimaryLineageContext,
    add_edge,
    add_edge_with_source_ids,
    add_record_node,
    issue,
    node_key,
    record_kind_for_ref,
    source_id,
    source_summary,
)


async def project_run_evidence_graph_primary_lineage(
    *,
    root: Path,
    session_id: str,
    run_id: str,
    generation_timestamp: str,
    execution_repository: Any,
    record_repository: Any,
    selected_views: list[str] | None = None,
) -> dict[str, Any]:
    normalized_run_id = str(run_id or "").strip()
    normalized_session_id = str(session_id or "").strip()
    views = list(selected_views or DEFAULT_VIEWS)

    if not normalized_session_id:
        return build_blocked_run_evidence_graph_payload(
            run_id=normalized_run_id or "unknown-run",
            generation_timestamp=generation_timestamp,
            selected_views=views,
            source_summaries=[
                source_summary(
                    source_id=f"source:artifact_root:{normalized_run_id or 'unknown-run'}",
                    authority_level="primary",
                    source_kind="artifact_root",
                    status="missing",
                    source_ref="runs/<session_id>/",
                    detail="session_id is required to validate the canonical artifact root",
                )
            ],
            issues=[issue(code="session_id_required", detail="session_id is required for V1 covered-run gating")],
        )

    session_root = Path(root) / "runs" / normalized_session_id
    if not await asyncio.to_thread(session_root.exists):
        return build_blocked_run_evidence_graph_payload(
            run_id=normalized_run_id or "unknown-run",
            generation_timestamp=generation_timestamp,
            selected_views=views,
            source_summaries=[
                source_summary(
                    source_id=f"source:artifact_root:{normalized_session_id}",
                    authority_level="primary",
                    source_kind="artifact_root",
                    status="missing",
                    source_ref=f"runs/{normalized_session_id}",
                    detail="selected run does not materialize under the canonical runs/<session_id>/ root",
                )
            ],
            issues=[
                issue(
                    code="run_artifact_root_missing",
                    detail=f"runs/{normalized_session_id} does not exist for the selected run",
                )
            ],
        )

    run = await execution_repository.get_run_record(run_id=normalized_run_id)
    if run is None:
        return build_blocked_run_evidence_graph_payload(
            run_id=normalized_run_id,
            generation_timestamp=generation_timestamp,
            selected_views=views,
            source_summaries=[
                source_summary(
                    source_id=f"source:RunRecord:{normalized_run_id}",
                    authority_level="primary",
                    source_kind="RunRecord",
                    status="missing",
                    source_ref=normalized_run_id,
                    detail="selected run has no first-class RunRecord lineage",
                )
            ],
            issues=[
                issue(
                    code="run_record_missing",
                    detail="selected run has no coherent first-class RunRecord lineage",
                    source_id=f"source:RunRecord:{normalized_run_id}",
                )
            ],
        )

    context = await collect_primary_lineage_context(
        run=run,
        generation_timestamp=generation_timestamp,
        selected_views=views,
        execution_repository=execution_repository,
        record_repository=record_repository,
    )
    if isinstance(context, dict):
        return context
    (
        supplemental_source_summaries,
        supplemental_issues,
        run_annotations,
        attempt_annotations_by_id,
        step_annotations_by_id,
    ) = await _load_supplemental_annotations(
        root=root,
        session_root=session_root,
        session_id=normalized_session_id,
        run_id=run.run_id,
        context=context,
    )
    return _build_primary_lineage_payload(
        context=context,
        generation_timestamp=generation_timestamp,
        selected_views=views,
        supplemental_source_summaries=supplemental_source_summaries,
        supplemental_issues=supplemental_issues,
        run_annotations=run_annotations,
        attempt_annotations_by_id=attempt_annotations_by_id,
        step_annotations_by_id=step_annotations_by_id,
    )


def _build_primary_lineage_payload(
    *,
    context: PrimaryLineageContext,
    generation_timestamp: str,
    selected_views: list[str],
    supplemental_source_summaries: list[dict[str, Any]],
    supplemental_issues: list[dict[str, Any]],
    run_annotations: dict[str, Any],
    attempt_annotations_by_id: dict[str, dict[str, Any]],
    step_annotations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    ref_to_node_id: dict[str, str] = {}
    resource_refs: set[str] = set()
    output_ref_to_step_id: dict[str, str] = {}
    run = context.run

    add_record_node(nodes, ref_to_node_id, run, family="run", record_id=run.run_id, record_ref=run.run_id)
    if run_annotations:
        nodes[node_key("run", run.run_id)]["attributes"].update(run_annotations)
    for attempt in context.attempts:
        add_record_node(nodes, ref_to_node_id, attempt, family="attempt", record_id=attempt.attempt_id, record_ref=attempt.attempt_id)
        if attempt.attempt_id in attempt_annotations_by_id:
            nodes[node_key("attempt", attempt.attempt_id)]["attributes"].update(
                attempt_annotations_by_id[attempt.attempt_id]
            )
        add_edge(edges, "run_to_attempt", node_key("run", run.run_id), node_key("attempt", attempt.attempt_id), [run.run_id, attempt.attempt_id], "RunRecord", "AttemptRecord")
    for attempt in context.attempts:
        for step in context.steps_by_attempt.get(attempt.attempt_id, []):
            add_record_node(nodes, ref_to_node_id, step, family="step", record_id=step.step_id, record_ref=step.step_id)
            if step.step_id in step_annotations_by_id:
                nodes[node_key("step", step.step_id)]["attributes"].update(step_annotations_by_id[step.step_id])
            add_edge(edges, "attempt_to_step", node_key("attempt", attempt.attempt_id), node_key("step", step.step_id), [attempt.attempt_id, step.step_id], "AttemptRecord", "StepRecord")
            output_ref = str(step.output_ref or "").strip()
            if output_ref:
                output_ref_to_step_id[output_ref] = step.step_id
    for checkpoint in context.checkpoint_by_id.values():
        add_record_node(nodes, ref_to_node_id, checkpoint, family="checkpoint", record_id=checkpoint.checkpoint_id, record_ref=checkpoint.checkpoint_id)
        if checkpoint.parent_ref in context.steps_by_id:
            add_edge(edges, "step_to_checkpoint", node_key("step", checkpoint.parent_ref), node_key("checkpoint", checkpoint.checkpoint_id), [checkpoint.parent_ref, checkpoint.checkpoint_id], "StepRecord", "CheckpointRecord")
            continue
        add_edge(edges, "attempt_to_checkpoint", node_key("attempt", checkpoint.parent_ref), node_key("checkpoint", checkpoint.checkpoint_id), [checkpoint.parent_ref, checkpoint.checkpoint_id], "AttemptRecord", "CheckpointRecord")
    for acceptance in context.checkpoint_acceptance_by_id.values():
        add_record_node(nodes, ref_to_node_id, acceptance, family="checkpoint_acceptance", record_id=acceptance.acceptance_id, record_ref=acceptance.acceptance_id)
        add_edge(edges, "checkpoint_to_checkpoint_acceptance", node_key("checkpoint", acceptance.checkpoint_id), node_key("checkpoint_acceptance", acceptance.acceptance_id), [acceptance.checkpoint_id, acceptance.acceptance_id], "CheckpointRecord", "CheckpointAcceptanceRecord")
    for effect in context.effects:
        add_record_node(nodes, ref_to_node_id, effect, family="effect", record_id=effect.journal_entry_id, record_ref=effect.journal_entry_id, alternate_refs=[effect.effect_id])
        add_edge(edges, "step_to_effect", node_key("step", effect.step_id), node_key("effect", effect.journal_entry_id), [effect.step_id, effect.journal_entry_id], "StepRecord", "EffectJournalEntryRecord")
        observed_result_ref = str(effect.observed_result_ref or "").strip()
        if observed_result_ref:
            effect_source_id = source_id("EffectJournalEntryRecord", effect.journal_entry_id)
            observation_node_id = _ensure_observation_node(
                nodes,
                observation_token=observed_result_ref,
                label=observed_result_ref,
                source_ids=[effect_source_id],
                attributes={
                    "observation_kind": "effect_observed_result",
                    "observation_ref": observed_result_ref,
                    "attempt_id": effect.attempt_id,
                    "step_id": effect.step_id,
                    "publication_timestamp": effect.publication_timestamp,
                },
            )
            add_edge_with_source_ids(
                edges,
                family="step_to_observation",
                source=node_key("step", effect.step_id),
                target=observation_node_id,
                source_ids=[source_id("StepRecord", effect.step_id), effect_source_id],
            )
            add_edge_with_source_ids(
                edges,
                family="observation_to_effect",
                source=observation_node_id,
                target=node_key("effect", effect.journal_entry_id),
                source_ids=[effect_source_id],
            )
    for decision in context.recovery_by_id.values():
        add_record_node(nodes, ref_to_node_id, decision, family="recovery_decision", record_id=decision.decision_id, record_ref=decision.decision_id)
        add_edge(edges, "attempt_to_recovery_decision", node_key("attempt", decision.failed_attempt_id), node_key("recovery_decision", decision.decision_id), [decision.failed_attempt_id, decision.decision_id], "AttemptRecord", "RecoveryDecisionRecord")
    if context.reservation is not None:
        add_record_node(nodes, ref_to_node_id, context.reservation, family="reservation", record_id=context.reservation.reservation_id, record_ref=context.reservation.reservation_id)
    if context.lease is not None:
        add_record_node(nodes, ref_to_node_id, context.lease, family="lease", record_id=context.lease.lease_id, record_ref=context.lease.lease_id)
    if context.resource is not None:
        add_record_node(nodes, ref_to_node_id, context.resource, family="resource", record_id=context.resource.resource_id, record_ref=context.resource.resource_id)
        resource_refs.add(context.resource.resource_id)
    if context.reservation is not None and context.lease is not None:
        add_edge(edges, "reservation_to_lease_promotion", node_key("reservation", context.reservation.reservation_id), node_key("lease", context.lease.lease_id), [context.reservation.reservation_id, context.lease.lease_id], "ReservationRecord", "LeaseRecord")
    if context.lease is not None and context.resource is not None:
        add_edge(edges, "lease_to_resource_authority", node_key("lease", context.lease.lease_id), node_key("resource", context.resource.resource_id), [context.lease.lease_id, context.resource.resource_id], "LeaseRecord", "ResourceRecord")
    if context.resource is not None and str(context.resource.current_observed_state or "").strip():
        resource_source_id = source_id("ResourceRecord", context.resource.resource_id)
        resource_observation_node_id = _ensure_observation_node(
            nodes,
            observation_token=f"resource_state:{context.resource.resource_id}",
            label=str(context.resource.current_observed_state),
            source_ids=[resource_source_id],
            attributes={
                "observation_kind": "resource_current_state",
                "current_observed_state": context.resource.current_observed_state,
                "resource_id": context.resource.resource_id,
                "last_observed_timestamp": context.resource.last_observed_timestamp,
                "provenance_ref": context.resource.provenance_ref,
            },
        )
        add_edge_with_source_ids(
            edges,
            family="observation_to_resource",
            source=resource_observation_node_id,
            target=node_key("resource", context.resource.resource_id),
            source_ids=[resource_source_id],
        )
    for reconciliation in context.reconciliations:
        add_record_node(nodes, ref_to_node_id, reconciliation, family="reconciliation", record_id=reconciliation.reconciliation_id, record_ref=reconciliation.reconciliation_id)
    if context.final_truth is not None:
        add_record_node(nodes, ref_to_node_id, context.final_truth, family="final_truth", record_id=context.final_truth.final_truth_record_id, record_ref=context.final_truth.final_truth_record_id)
        add_edge(edges, "final_truth_to_run", node_key("final_truth", context.final_truth.final_truth_record_id), node_key("run", run.run_id), [context.final_truth.final_truth_record_id, run.run_id], "FinalTruthRecord", "RunRecord")
        authoritative_result_ref = str(context.final_truth.authoritative_result_ref or "").strip()
        if authoritative_result_ref:
            final_truth_source_id = source_id("FinalTruthRecord", context.final_truth.final_truth_record_id)
            observation_node_id = _ensure_observation_node(
                nodes,
                observation_token=authoritative_result_ref,
                label=authoritative_result_ref,
                source_ids=[final_truth_source_id],
                attributes={
                    "observation_kind": "final_truth_authoritative_result",
                    "observation_ref": authoritative_result_ref,
                    "final_truth_record_id": context.final_truth.final_truth_record_id,
                    "closure_basis": context.final_truth.closure_basis.value,
                },
            )
            observed_step_id = output_ref_to_step_id.get(authoritative_result_ref)
            if observed_step_id is not None:
                add_edge_with_source_ids(
                    edges,
                    family="step_to_observation",
                    source=node_key("step", observed_step_id),
                    target=observation_node_id,
                    source_ids=[source_id("StepRecord", observed_step_id), final_truth_source_id],
                )
            add_edge_with_source_ids(
                edges,
                family="observation_to_final_truth",
                source=observation_node_id,
                target=node_key("final_truth", context.final_truth.final_truth_record_id),
                source_ids=[final_truth_source_id],
            )
    if context.linked_reconciliation_id and context.final_truth is not None:
        add_edge(edges, "reconciliation_to_final_truth", node_key("reconciliation", context.linked_reconciliation_id), node_key("final_truth", context.final_truth.final_truth_record_id), [context.linked_reconciliation_id, context.final_truth.final_truth_record_id], "ReconciliationRecord", "FinalTruthRecord")
    for action in context.operator_actions:
        add_record_node(nodes, ref_to_node_id, action, family="operator_action", record_id=action.action_id, record_ref=action.action_id)
        transition_refs = list(action.affected_transition_refs)
        resource_action_refs = list(action.affected_resource_refs)
        target_ref = str(action.target_ref or "").strip()
        if not transition_refs and target_ref and target_ref in ref_to_node_id and target_ref not in resource_refs:
            transition_refs.append(target_ref)
        if not resource_action_refs and target_ref and target_ref in resource_refs:
            resource_action_refs.append(target_ref)
        for transition_ref in sorted({ref for ref in transition_refs if ref in ref_to_node_id}):
            add_edge(edges, "operator_action_to_affected_transition", node_key("operator_action", action.action_id), ref_to_node_id[transition_ref], [action.action_id, transition_ref], "OperatorActionRecord", record_kind_for_ref(transition_ref, nodes, ref_to_node_id))
        for resource_ref in sorted({ref for ref in resource_action_refs if ref in ref_to_node_id}):
            add_edge(
                edges,
                "operator_action_to_affected_resource",
                node_key("operator_action", action.action_id),
                ref_to_node_id[resource_ref],
                [action.action_id, resource_ref],
                "OperatorActionRecord",
                record_kind_for_ref(resource_ref, nodes, ref_to_node_id),
            )

    source_summaries = list(context.sources.values()) + list(supplemental_source_summaries)
    issues = list(supplemental_issues)
    graph_result = "degraded" if issues or any(summary["status"] != "present" for summary in source_summaries) else "complete"
    return build_run_evidence_graph_payload(
        run_id=run.run_id,
        generation_timestamp=generation_timestamp,
        graph_result=graph_result,
        selected_views=selected_views,
        source_summaries=source_summaries,
        issues=issues,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
    )


async def _load_supplemental_annotations(
    *,
    root: Path,
    session_root: Path,
    session_id: str,
    run_id: str,
    context: PrimaryLineageContext,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    supplemental = await load_supplemental_projection(
        root=root,
        session_root=session_root,
        session_id=session_id,
        run_id=run_id,
        context=context,
    )
    return (
        supplemental.source_summaries,
        supplemental.issues,
        supplemental.run_annotations,
        supplemental.attempt_annotations_by_id,
        supplemental.step_annotations_by_id,
    )


def _ensure_observation_node(
    nodes: dict[str, dict[str, Any]],
    *,
    observation_token: str,
    label: str,
    source_ids: list[str],
    attributes: dict[str, Any],
) -> str:
    node_id = node_key("observation", observation_token)
    payload = nodes.get(node_id)
    if payload is None:
        nodes[node_id] = {
            "id": node_id,
            "family": "observation",
            "label": label,
            "source_ids": sorted({str(token).strip() for token in source_ids if str(token).strip()}),
            "attributes": dict(attributes),
        }
        return node_id
    payload["source_ids"] = sorted({*payload.get("source_ids", []), *[str(token).strip() for token in source_ids if str(token).strip()]})
    payload_attributes = dict(payload.get("attributes") or {})
    payload_attributes.update(attributes)
    payload["attributes"] = payload_attributes
    return node_id


__all__ = ["project_run_evidence_graph_primary_lineage"]
