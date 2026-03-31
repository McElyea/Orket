from __future__ import annotations

from typing import Any

from orket.core.domain import ClosureBasisClassification
from orket.runtime.run_evidence_graph_projection_support import (
    PrimaryLineageContext,
    TERMINAL_RUN_STATES,
    blocked_payload,
    load_latest_lease_record,
    load_latest_reservation_record,
    load_latest_resource_record,
    put_source,
    record_source_summary,
    source_id,
    source_summary,
)


async def collect_primary_lineage_context(
    *,
    run: Any,
    generation_timestamp: str,
    selected_views: list[str],
    execution_repository: Any,
    record_repository: Any,
) -> PrimaryLineageContext | dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    put_source(sources, record_source_summary(record_kind="RunRecord", record_id=run.run_id))

    attempts = await execution_repository.list_attempt_records(run_id=run.run_id)
    if not attempts:
        put_source(
            sources,
            source_summary(
                source_id=source_id("AttemptRecord", run.run_id),
                authority_level="primary",
                source_kind="AttemptRecord",
                status="missing",
                source_ref=run.run_id,
                detail="V1-covered runs require at least one coherent AttemptRecord",
            ),
        )
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="attempt_lineage_missing",
            detail="selected run is outside the V1 covered-run set because no AttemptRecord lineage exists",
            source_id=source_id("AttemptRecord", run.run_id),
        )

    attempts_by_id: dict[str, Any] = {}
    for ordinal, attempt in enumerate(attempts, start=1):
        put_source(sources, record_source_summary(record_kind="AttemptRecord", record_id=attempt.attempt_id))
        if attempt.run_id != run.run_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="attempt_run_lineage_mismatch",
                detail=f"attempt {attempt.attempt_id} does not belong to run {run.run_id}",
                source_id=source_id("AttemptRecord", attempt.attempt_id),
            )
        if attempt.attempt_ordinal != ordinal:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="attempt_ordinal_gap",
                detail=f"attempt ordinals for run {run.run_id} are not sequential from 1",
                source_id=source_id("AttemptRecord", attempt.attempt_id),
            )
        attempts_by_id[attempt.attempt_id] = attempt

    if run.current_attempt_id:
        current_attempt = await execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
        if current_attempt is None:
            put_source(
                sources,
                source_summary(
                    source_id=source_id("AttemptRecord", run.current_attempt_id),
                    authority_level="primary",
                    source_kind="AttemptRecord",
                    status="missing",
                    source_ref=run.current_attempt_id,
                    detail="run.current_attempt_id points to a missing AttemptRecord",
                ),
            )
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="run_current_attempt_missing",
                detail=f"run.current_attempt_id {run.current_attempt_id} does not resolve to an AttemptRecord",
                source_id=source_id("AttemptRecord", run.current_attempt_id),
            )
        if current_attempt.run_id != run.run_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="run_current_attempt_run_lineage_mismatch",
                detail=f"run.current_attempt_id {run.current_attempt_id} resolves outside run {run.run_id}",
                source_id=source_id("AttemptRecord", current_attempt.attempt_id),
            )

    steps_by_id: dict[str, Any] = {}
    steps_by_attempt: dict[str, list[Any]] = {}
    for attempt in attempts:
        steps = await execution_repository.list_step_records(attempt_id=attempt.attempt_id)
        steps_by_attempt[attempt.attempt_id] = steps
        for step in steps:
            put_source(sources, record_source_summary(record_kind="StepRecord", record_id=step.step_id))
            if step.attempt_id != attempt.attempt_id:
                return blocked_payload(
                    run_id=run.run_id,
                    generation_timestamp=generation_timestamp,
                    selected_views=selected_views,
                    sources=sources,
                    code="step_attempt_lineage_mismatch",
                    detail=f"step {step.step_id} does not belong to attempt {attempt.attempt_id}",
                    source_id=source_id("StepRecord", step.step_id),
                )
            steps_by_id[step.step_id] = step

    recovery_by_id: dict[str, Any] = {}
    for attempt in attempts:
        decision_id = str(attempt.recovery_decision_id or "").strip()
        if not decision_id:
            continue
        decision = await record_repository.get_recovery_decision(decision_id=decision_id)
        if decision is None:
            put_source(
                sources,
                source_summary(
                    source_id=source_id("RecoveryDecisionRecord", decision_id),
                    authority_level="primary",
                    source_kind="RecoveryDecisionRecord",
                    status="missing",
                    source_ref=decision_id,
                    detail="attempt recovery_decision_id points to a missing RecoveryDecisionRecord",
                ),
            )
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="recovery_decision_missing",
                detail=f"attempt {attempt.attempt_id} references missing recovery decision {decision_id}",
                source_id=source_id("RecoveryDecisionRecord", decision_id),
            )
        put_source(sources, record_source_summary(record_kind="RecoveryDecisionRecord", record_id=decision.decision_id))
        if decision.run_id != run.run_id or decision.failed_attempt_id != attempt.attempt_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="recovery_decision_lineage_mismatch",
                detail=f"recovery decision {decision.decision_id} does not preserve failed-attempt lineage for {attempt.attempt_id}",
                source_id=source_id("RecoveryDecisionRecord", decision.decision_id),
            )
        if decision.new_attempt_id and decision.new_attempt_id not in attempts_by_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="recovery_decision_target_attempt_missing",
                detail=f"recovery decision {decision.decision_id} references missing new attempt {decision.new_attempt_id}",
                source_id=source_id("RecoveryDecisionRecord", decision.decision_id),
            )
        if decision.resumed_attempt_id and decision.resumed_attempt_id not in attempts_by_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="recovery_decision_target_attempt_missing",
                detail=f"recovery decision {decision.decision_id} references missing resumed attempt {decision.resumed_attempt_id}",
                source_id=source_id("RecoveryDecisionRecord", decision.decision_id),
            )
        recovery_by_id[decision.decision_id] = decision

    checkpoint_by_id: dict[str, Any] = {}
    checkpoint_acceptance_by_id: dict[str, Any] = {}
    for attempt in attempts:
        checkpoints = await record_repository.list_checkpoints(parent_ref=attempt.attempt_id)
        for checkpoint in checkpoints:
            put_source(
                sources,
                record_source_summary(record_kind="CheckpointRecord", record_id=checkpoint.checkpoint_id),
            )
            checkpoint_by_id[checkpoint.checkpoint_id] = checkpoint
            acceptance = await record_repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
            if acceptance is None:
                continue
            put_source(
                sources,
                record_source_summary(
                    record_kind="CheckpointAcceptanceRecord",
                    record_id=acceptance.acceptance_id,
                ),
            )
            checkpoint_acceptance_by_id[acceptance.acceptance_id] = acceptance

    for step in steps_by_id.values():
        checkpoints = await record_repository.list_checkpoints(parent_ref=step.step_id)
        for checkpoint in checkpoints:
            put_source(sources, record_source_summary(record_kind="CheckpointRecord", record_id=checkpoint.checkpoint_id))
            checkpoint_by_id[checkpoint.checkpoint_id] = checkpoint
            acceptance = await record_repository.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
            if acceptance is None:
                continue
            put_source(
                sources,
                record_source_summary(
                    record_kind="CheckpointAcceptanceRecord",
                    record_id=acceptance.acceptance_id,
                ),
            )
            checkpoint_acceptance_by_id[acceptance.acceptance_id] = acceptance

    effects = await record_repository.list_effect_journal_entries(run_id=run.run_id)
    for effect in effects:
        put_source(sources, record_source_summary(record_kind="EffectJournalEntryRecord", record_id=effect.journal_entry_id))
        step = steps_by_id.get(effect.step_id)
        attempt = attempts_by_id.get(effect.attempt_id)
        if step is None:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="effect_step_lineage_missing",
                detail=f"effect journal entry {effect.journal_entry_id} references missing step {effect.step_id}",
                source_id=source_id("EffectJournalEntryRecord", effect.journal_entry_id),
            )
        if attempt is None or step.attempt_id != effect.attempt_id:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="effect_attempt_lineage_mismatch",
                detail=f"effect journal entry {effect.journal_entry_id} does not preserve attempt lineage",
                source_id=source_id("EffectJournalEntryRecord", effect.journal_entry_id),
            )

    reservation = await load_latest_reservation_record(record_repository=record_repository, run=run)
    lease = await load_latest_lease_record(record_repository=record_repository, run=run)
    resource = await load_latest_resource_record(record_repository=record_repository, run=run)
    if reservation is not None:
        put_source(sources, record_source_summary(record_kind="ReservationRecord", record_id=reservation.reservation_id))
    if lease is not None:
        put_source(sources, record_source_summary(record_kind="LeaseRecord", record_id=lease.lease_id))
    if resource is not None:
        put_source(sources, record_source_summary(record_kind="ResourceRecord", record_id=resource.resource_id))
    if reservation is not None and reservation.promoted_lease_id and (lease is None or lease.lease_id != reservation.promoted_lease_id):
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="reservation_lease_lineage_missing",
            detail=f"reservation {reservation.reservation_id} promotes to missing lease {reservation.promoted_lease_id}",
            source_id=source_id("ReservationRecord", reservation.reservation_id),
        )
    if lease is not None and lease.source_reservation_id and (reservation is None or reservation.reservation_id != lease.source_reservation_id):
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="lease_reservation_lineage_missing",
            detail=f"lease {lease.lease_id} references missing reservation {lease.source_reservation_id}",
            source_id=source_id("LeaseRecord", lease.lease_id),
        )
    if lease is not None and resource is None:
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="lease_resource_lineage_missing",
            detail=f"lease {lease.lease_id} does not have a corresponding ResourceRecord for {lease.resource_id}",
            source_id=source_id("LeaseRecord", lease.lease_id),
        )
    if lease is not None and resource is not None and lease.resource_id != resource.resource_id:
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="lease_resource_lineage_mismatch",
            detail=f"lease {lease.lease_id} points to {lease.resource_id} but resource lineage resolved to {resource.resource_id}",
            source_id=source_id("LeaseRecord", lease.lease_id),
        )

    final_truth = await record_repository.get_final_truth(run_id=run.run_id)
    if final_truth is not None:
        put_source(sources, record_source_summary(record_kind="FinalTruthRecord", record_id=final_truth.final_truth_record_id))
    if run.lifecycle_state in TERMINAL_RUN_STATES and final_truth is None:
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="terminal_final_truth_missing",
            detail=f"terminal run {run.run_id} does not have a coherent FinalTruthRecord closure",
            source_id=source_id("RunRecord", run.run_id),
        )
    if run.final_truth_record_id and (final_truth is None or final_truth.final_truth_record_id != run.final_truth_record_id):
        return blocked_payload(
            run_id=run.run_id,
            generation_timestamp=generation_timestamp,
            selected_views=selected_views,
            sources=sources,
            code="run_final_truth_mismatch",
            detail=f"run {run.run_id} references final truth {run.final_truth_record_id} but the repository does not agree",
            source_id=source_id("RunRecord", run.run_id),
        )

    reconciliations = await record_repository.list_reconciliation_records(target_ref=run.run_id)
    for reconciliation in reconciliations:
        put_source(sources, record_source_summary(record_kind="ReconciliationRecord", record_id=reconciliation.reconciliation_id))

    linked_reconciliation_id = ""
    if final_truth is not None and final_truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED:
        linked_reconciliation_id = str(final_truth.authoritative_result_ref or "").strip()
        reconciliation_ids = {record.reconciliation_id for record in reconciliations}
        if linked_reconciliation_id:
            if linked_reconciliation_id not in reconciliation_ids:
                return blocked_payload(
                    run_id=run.run_id,
                    generation_timestamp=generation_timestamp,
                    selected_views=selected_views,
                    sources=sources,
                    code="reconciliation_final_truth_link_missing",
                    detail=f"final truth {final_truth.final_truth_record_id} points to missing reconciliation {linked_reconciliation_id}",
                    source_id=source_id("FinalTruthRecord", final_truth.final_truth_record_id),
                )
        elif len(reconciliations) == 1:
            linked_reconciliation_id = reconciliations[0].reconciliation_id
        else:
            return blocked_payload(
                run_id=run.run_id,
                generation_timestamp=generation_timestamp,
                selected_views=selected_views,
                sources=sources,
                code="reconciliation_final_truth_ambiguous",
                detail=f"reconciliation-closed final truth for run {run.run_id} is ambiguous without an authoritative reconciliation ref",
                source_id=source_id("FinalTruthRecord", final_truth.final_truth_record_id),
            )

    operator_actions = await record_repository.list_operator_actions(target_ref=run.run_id)
    for action in operator_actions:
        put_source(sources, record_source_summary(record_kind="OperatorActionRecord", record_id=action.action_id))

    return PrimaryLineageContext(
        run=run,
        attempts=attempts,
        attempts_by_id=attempts_by_id,
        steps_by_attempt=steps_by_attempt,
        steps_by_id=steps_by_id,
        recovery_by_id=recovery_by_id,
        checkpoint_by_id=checkpoint_by_id,
        checkpoint_acceptance_by_id=checkpoint_acceptance_by_id,
        effects=effects,
        reservation=reservation,
        lease=lease,
        resource=resource,
        final_truth=final_truth,
        reconciliations=reconciliations,
        linked_reconciliation_id=linked_reconciliation_id,
        operator_actions=operator_actions,
        sources=sources,
    )


__all__ = ["collect_primary_lineage_context"]
