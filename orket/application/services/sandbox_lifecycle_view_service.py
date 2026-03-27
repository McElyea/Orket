from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from orket.application.services.sandbox_control_plane_resource_service import (
    SandboxControlPlaneResourceService,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleRecord


@dataclass(frozen=True)
class SandboxLifecycleOperatorView:
    sandbox_id: str
    compose_project: str
    state: str
    cleanup_state: str
    terminal_reason: str | None
    owner_instance_id: str | None
    cleanup_owner_instance_id: str | None
    lease_expires_at: str | None
    heartbeat_age_seconds: int | None
    restart_summary: dict[str, object] = field(default_factory=dict)
    cleanup_eligible: bool = False
    cleanup_due_at: str | None = None
    requires_reconciliation: bool = False
    control_plane_run_state: str | None = None
    control_plane_current_attempt_id: str | None = None
    control_plane_current_attempt_state: str | None = None
    control_plane_recovery_decision_id: str | None = None
    control_plane_recovery_action: str | None = None
    control_plane_checkpoint_id: str | None = None
    control_plane_checkpoint_resumability_class: str | None = None
    control_plane_checkpoint_acceptance_outcome: str | None = None
    control_plane_reconciliation_id: str | None = None
    control_plane_divergence_class: str | None = None
    control_plane_safe_continuation_class: str | None = None
    control_plane_reservation_status: str | None = None
    control_plane_lease_status: str | None = None
    control_plane_resource_id: str | None = None
    control_plane_resource_kind: str | None = None
    control_plane_resource_state: str | None = None
    control_plane_resource_orphan_classification: str | None = None
    final_truth_record_id: str | None = None
    control_plane_final_result_class: str | None = None
    control_plane_final_closure_basis: str | None = None
    control_plane_final_terminality_basis: str | None = None
    control_plane_final_evidence_sufficiency_class: str | None = None
    control_plane_final_residual_uncertainty_class: str | None = None
    control_plane_final_degradation_class: str | None = None
    control_plane_final_authoritative_result_ref: str | None = None
    control_plane_final_authority_sources: list[str] = field(default_factory=list)
    effect_journal_entry_count: int = 0
    latest_effect_journal_entry_id: str | None = None
    latest_effect_id: str | None = None
    latest_effect_intended_target_ref: str | None = None
    latest_effect_observed_result_ref: str | None = None
    latest_effect_authorization_basis_ref: str | None = None
    latest_effect_integrity_verification_ref: str | None = None
    latest_effect_uncertainty_classification: str | None = None
    operator_action_count: int = 0
    latest_operator_action: dict[str, object] | None = None


class SandboxLifecycleViewService:
    """Projects durable lifecycle records into operator-facing read models."""

    def __init__(self, repository, *, control_plane_repository=None, control_plane_execution_repository=None):
        self.repository = repository
        self.control_plane_repository = control_plane_repository
        self.control_plane_execution_repository = control_plane_execution_repository

    async def list_views(self, *, observed_at: str) -> list[SandboxLifecycleOperatorView]:
        records = await self.repository.list_records()
        views = []
        for record in records:
            events = await self.repository.list_events(record.sandbox_id)
            operator_actions = await self._operator_actions_for_record(record)
            run_record, attempt_record = await self._execution_authority_for_record(record)
            control_plane_summary = await self._control_plane_record_summary(record, attempt_record=attempt_record)
            views.append(
                self.build_view(
                    record=record,
                    observed_at=observed_at,
                    events=events,
                    operator_actions=operator_actions,
                    run_record=run_record,
                    attempt_record=attempt_record,
                    control_plane_summary=control_plane_summary,
                )
            )
        return sorted(views, key=lambda item: (item.cleanup_due_at or "", item.sandbox_id))

    def build_view(
        self,
        *,
        record: SandboxLifecycleRecord,
        observed_at: str,
        events: list | None = None,
        operator_actions: list | None = None,
        run_record=None,
        attempt_record=None,
        control_plane_summary: dict[str, object] | None = None,
    ) -> SandboxLifecycleOperatorView:
        heartbeat_age = self._heartbeat_age_seconds(record.last_heartbeat_at, observed_at)
        cleanup_eligible = (
            record.state in {SandboxState.TERMINAL, SandboxState.RECLAIMABLE, SandboxState.ORPHANED}
            and record.cleanup_state in {CleanupState.NONE, CleanupState.SCHEDULED}
            and not record.requires_reconciliation
        )
        latest_operator_action = self._latest_operator_action(operator_actions or [])
        return SandboxLifecycleOperatorView(
            sandbox_id=record.sandbox_id,
            compose_project=record.compose_project,
            state=record.state.value,
            cleanup_state=record.cleanup_state.value,
            terminal_reason=record.terminal_reason.value if record.terminal_reason else None,
            owner_instance_id=record.owner_instance_id,
            cleanup_owner_instance_id=record.cleanup_owner_instance_id,
            lease_expires_at=record.lease_expires_at,
            heartbeat_age_seconds=heartbeat_age,
            restart_summary=self._restart_summary(events or []),
            cleanup_eligible=cleanup_eligible,
            cleanup_due_at=record.cleanup_due_at,
            requires_reconciliation=record.requires_reconciliation,
            control_plane_run_state=None if run_record is None else run_record.lifecycle_state.value,
            control_plane_current_attempt_id=None if run_record is None else run_record.current_attempt_id,
            control_plane_current_attempt_state=None if attempt_record is None else attempt_record.attempt_state.value,
            control_plane_recovery_decision_id=None
            if control_plane_summary is None
            else control_plane_summary["recovery_decision_id"],
            control_plane_recovery_action=None
            if control_plane_summary is None
            else control_plane_summary["recovery_action"],
            control_plane_checkpoint_id=None
            if control_plane_summary is None
            else control_plane_summary["checkpoint_id"],
            control_plane_checkpoint_resumability_class=None
            if control_plane_summary is None
            else control_plane_summary["checkpoint_resumability_class"],
            control_plane_checkpoint_acceptance_outcome=None
            if control_plane_summary is None
            else control_plane_summary["checkpoint_acceptance_outcome"],
            control_plane_reconciliation_id=None
            if control_plane_summary is None
            else control_plane_summary["reconciliation_id"],
            control_plane_divergence_class=None
            if control_plane_summary is None
            else control_plane_summary["divergence_class"],
            control_plane_safe_continuation_class=None
            if control_plane_summary is None
            else control_plane_summary["safe_continuation_class"],
            control_plane_reservation_status=None
            if control_plane_summary is None
            else control_plane_summary["reservation_status"],
            control_plane_lease_status=None if control_plane_summary is None else control_plane_summary["lease_status"],
            control_plane_resource_id=None if control_plane_summary is None else control_plane_summary["resource_id"],
            control_plane_resource_kind=None
            if control_plane_summary is None
            else control_plane_summary["resource_kind"],
            control_plane_resource_state=None
            if control_plane_summary is None
            else control_plane_summary["resource_state"],
            control_plane_resource_orphan_classification=None
            if control_plane_summary is None
            else control_plane_summary["resource_orphan_classification"],
            final_truth_record_id=None if run_record is None else run_record.final_truth_record_id,
            control_plane_final_result_class=None
            if control_plane_summary is None
            else control_plane_summary["final_result_class"],
            control_plane_final_closure_basis=None
            if control_plane_summary is None
            else control_plane_summary["final_closure_basis"],
            control_plane_final_terminality_basis=None
            if control_plane_summary is None
            else control_plane_summary["final_terminality_basis"],
            control_plane_final_evidence_sufficiency_class=None
            if control_plane_summary is None
            else control_plane_summary["final_evidence_sufficiency_class"],
            control_plane_final_residual_uncertainty_class=None
            if control_plane_summary is None
            else control_plane_summary["final_residual_uncertainty_class"],
            control_plane_final_degradation_class=None
            if control_plane_summary is None
            else control_plane_summary["final_degradation_class"],
            control_plane_final_authoritative_result_ref=None
            if control_plane_summary is None
            else control_plane_summary["final_authoritative_result_ref"],
            control_plane_final_authority_sources=[]
            if control_plane_summary is None
            else control_plane_summary["final_authority_sources"],
            effect_journal_entry_count=0 if control_plane_summary is None else control_plane_summary["effect_count"],
            latest_effect_journal_entry_id=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_journal_entry_id"],
            latest_effect_id=None if control_plane_summary is None else control_plane_summary["latest_effect_id"],
            latest_effect_intended_target_ref=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_intended_target_ref"],
            latest_effect_observed_result_ref=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_observed_result_ref"],
            latest_effect_authorization_basis_ref=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_authorization_basis_ref"],
            latest_effect_integrity_verification_ref=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_integrity_verification_ref"],
            latest_effect_uncertainty_classification=None
            if control_plane_summary is None
            else control_plane_summary["latest_effect_uncertainty_classification"],
            operator_action_count=len(operator_actions or []),
            latest_operator_action=latest_operator_action,
        )

    @staticmethod
    def _heartbeat_age_seconds(last_heartbeat_at: str | None, observed_at: str) -> int | None:
        if not last_heartbeat_at:
            return None
        start = datetime.fromisoformat(last_heartbeat_at)
        end = datetime.fromisoformat(observed_at)
        return max(0, int((end - start).total_seconds()))

    @staticmethod
    def _restart_summary(events: list) -> dict[str, object]:
        for event in sorted(events, key=lambda item: (item.created_at, item.event_id), reverse=True):
            if str(event.event_type).startswith("sandbox.runtime_health") or str(event.event_type).startswith(
                "sandbox.restart_loop"
            ):
                if isinstance(event.payload, dict):
                    return dict(event.payload)
        return {}

    async def _operator_actions_for_record(self, record: SandboxLifecycleRecord) -> list:
        if self.control_plane_repository is None or record.run_id is None:
            return []
        return await self.control_plane_repository.list_operator_actions(target_ref=record.run_id)

    async def _execution_authority_for_record(self, record: SandboxLifecycleRecord) -> tuple[object | None, object | None]:
        if self.control_plane_execution_repository is None or record.run_id is None:
            return None, None
        run_record = await self.control_plane_execution_repository.get_run_record(run_id=record.run_id)
        if run_record is None:
            return None, None
        attempt_record = None
        if run_record.current_attempt_id is not None:
            attempt_record = await self.control_plane_execution_repository.get_attempt_record(
                attempt_id=run_record.current_attempt_id
            )
        if attempt_record is None:
            attempts = await self.control_plane_execution_repository.list_attempt_records(run_id=record.run_id)
            if attempts:
                attempt_record = attempts[-1]
        return run_record, attempt_record

    async def _control_plane_record_summary(
        self,
        record: SandboxLifecycleRecord,
        *,
        attempt_record,
    ) -> dict[str, object]:
        if self.control_plane_repository is None:
            return {
                "recovery_action": None,
                "recovery_decision_id": None,
                "checkpoint_id": None,
                "checkpoint_resumability_class": None,
                "checkpoint_acceptance_outcome": None,
                "reconciliation_id": None,
                "divergence_class": None,
                "safe_continuation_class": None,
                "reservation_status": None,
                "lease_status": None,
                "resource_id": None,
                "resource_kind": None,
                "resource_state": None,
                "resource_orphan_classification": None,
                "final_result_class": None,
                "final_closure_basis": None,
                "final_terminality_basis": None,
                "final_evidence_sufficiency_class": None,
                "final_residual_uncertainty_class": None,
                "final_degradation_class": None,
                "final_authoritative_result_ref": None,
                "final_authority_sources": [],
                "effect_count": 0,
                "latest_effect_journal_entry_id": None,
                "latest_effect_id": None,
                "latest_effect_intended_target_ref": None,
                "latest_effect_observed_result_ref": None,
                "latest_effect_authorization_basis_ref": None,
                "latest_effect_integrity_verification_ref": None,
                "latest_effect_uncertainty_classification": None,
            }
        final_truth = None
        if record.run_id is not None:
            final_truth = await self.control_plane_repository.get_final_truth(run_id=record.run_id)
        recovery_decision = None
        recovery_decision_id = None
        attempts = []
        if self.control_plane_execution_repository is not None and record.run_id is not None:
            attempts = await self.control_plane_execution_repository.list_attempt_records(run_id=record.run_id)
        if attempt_record is not None and attempt_record.recovery_decision_id is not None:
            recovery_decision_id = attempt_record.recovery_decision_id
        elif attempts:
            for candidate in reversed(attempts):
                if candidate.recovery_decision_id is not None:
                    recovery_decision_id = candidate.recovery_decision_id
                    break
        if recovery_decision_id is not None:
            recovery_decision = await self.control_plane_repository.get_recovery_decision(
                decision_id=recovery_decision_id
            )
        checkpoint = None
        checkpoint_acceptance = None
        checkpoint_attempt_ids = []
        if attempt_record is not None:
            checkpoint_attempt_ids.append(attempt_record.attempt_id)
        if attempts:
            checkpoint_attempt_ids.extend(
                candidate.attempt_id for candidate in reversed(attempts) if candidate.attempt_id not in checkpoint_attempt_ids
            )
        for attempt_id in checkpoint_attempt_ids:
            checkpoints = await self.control_plane_repository.list_checkpoints(parent_ref=attempt_id)
            if checkpoints:
                checkpoint = checkpoints[-1]
                checkpoint_acceptance = await self.control_plane_repository.get_checkpoint_acceptance(
                    checkpoint_id=checkpoint.checkpoint_id
                )
                break
        reservation = await self.control_plane_repository.get_latest_reservation_record(
            reservation_id=f"sandbox-reservation:{record.sandbox_id}"
        )
        lease = await self.control_plane_repository.get_latest_lease_record(
            lease_id=f"sandbox-lease:{record.sandbox_id}"
        )
        resource = await self.control_plane_repository.get_latest_resource_record(
            resource_id=SandboxControlPlaneResourceService.resource_id_for_sandbox(record.sandbox_id)
        )
        reconciliation = None if record.run_id is None else await self.control_plane_repository.get_latest_reconciliation_record(
            target_ref=record.run_id
        )
        entries = [] if record.run_id is None else await self.control_plane_repository.list_effect_journal_entries(
            run_id=record.run_id
        )
        latest_entry = entries[-1] if entries else None
        return {
            "recovery_action": None if recovery_decision is None else recovery_decision.authorized_next_action.value,
            "recovery_decision_id": recovery_decision_id,
            "checkpoint_id": None if checkpoint is None else checkpoint.checkpoint_id,
            "checkpoint_resumability_class": None
            if checkpoint is None
            else checkpoint.resumability_class.value,
            "checkpoint_acceptance_outcome": None
            if checkpoint_acceptance is None
            else checkpoint_acceptance.outcome.value,
            "reconciliation_id": None if reconciliation is None else reconciliation.reconciliation_id,
            "divergence_class": None if reconciliation is None else reconciliation.divergence_class.value,
            "safe_continuation_class": None
            if reconciliation is None
            else reconciliation.safe_continuation_class.value,
            "reservation_status": None if reservation is None else reservation.status.value,
            "lease_status": None if lease is None else lease.status.value,
            "resource_id": None if resource is None else resource.resource_id,
            "resource_kind": None if resource is None else resource.resource_kind,
            "resource_state": None if resource is None else resource.current_observed_state,
            "resource_orphan_classification": None
            if resource is None
            else resource.orphan_classification.value,
            "final_result_class": None if final_truth is None else final_truth.result_class.value,
            "final_closure_basis": None if final_truth is None else final_truth.closure_basis.value,
            "final_terminality_basis": None if final_truth is None else final_truth.terminality_basis.value,
            "final_evidence_sufficiency_class": None
            if final_truth is None
            else final_truth.evidence_sufficiency_classification.value,
            "final_residual_uncertainty_class": None
            if final_truth is None
            else final_truth.residual_uncertainty_classification.value,
            "final_degradation_class": None if final_truth is None else final_truth.degradation_classification.value,
            "final_authoritative_result_ref": None if final_truth is None else final_truth.authoritative_result_ref,
            "final_authority_sources": []
            if final_truth is None
            else [source.value for source in final_truth.authority_sources],
            "effect_count": len(entries),
            "latest_effect_journal_entry_id": None if latest_entry is None else latest_entry.journal_entry_id,
            "latest_effect_id": None if latest_entry is None else latest_entry.effect_id,
            "latest_effect_intended_target_ref": None if latest_entry is None else latest_entry.intended_target_ref,
            "latest_effect_observed_result_ref": None if latest_entry is None else latest_entry.observed_result_ref,
            "latest_effect_authorization_basis_ref": None
            if latest_entry is None
            else latest_entry.authorization_basis_ref,
            "latest_effect_integrity_verification_ref": None
            if latest_entry is None
            else latest_entry.integrity_verification_ref,
            "latest_effect_uncertainty_classification": None
            if latest_entry is None
            else latest_entry.uncertainty_classification.value,
        }

    @staticmethod
    def _latest_operator_action(operator_actions: list) -> dict[str, object] | None:
        if not operator_actions:
            return None
        latest = sorted(operator_actions, key=lambda item: (item.timestamp, item.action_id))[-1]
        return {
            "action_id": latest.action_id,
            "input_class": latest.input_class.value,
            "command_class": None if latest.command_class is None else latest.command_class.value,
            "risk_acceptance_scope": latest.risk_acceptance_scope,
            "attestation_scope": latest.attestation_scope,
            "attestation_payload": dict(latest.attestation_payload),
            "precondition_basis_ref": latest.precondition_basis_ref,
            "timestamp": latest.timestamp,
            "actor_ref": latest.actor_ref,
            "receipt_refs": list(latest.receipt_refs),
            "affected_transition_refs": list(latest.affected_transition_refs),
            "affected_resource_refs": list(latest.affected_resource_refs),
        }
