from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots
from orket.application.services.control_plane_workload_catalog import (
    CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF,
    sandbox_runtime_workload_for_tech_stack,
)
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    RecoveryDecisionRecord,
    RunRecord,
    WorkloadRecord,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    RecoveryActionClass,
    RunState,
    SideEffectBoundaryClass,
    infer_failure_taxonomy,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.core.domain.sandbox_lifecycle import TerminalReason


class SandboxControlPlaneExecutionError(ValueError):
    """Raised when sandbox execution authority cannot be published truthfully."""


class SandboxControlPlaneExecutionService:
    """Publishes sandbox run and attempt authority into the ControlPlane store."""

    def __init__(
        self,
        *,
        repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService | None = None,
    ) -> None:
        self.repository = repository
        self.publication = publication

    async def initialize_execution(
        self,
        *,
        sandbox_id: str,
        run_id: str,
        workload: WorkloadRecord,
        compose_project: str,
        workspace_path: str,
        configuration_payload: dict[str, object],
        creation_timestamp: str,
        admission_decision_receipt_ref: str,
        policy: SandboxLifecyclePolicy,
    ) -> tuple[RunRecord, AttemptRecord]:
        attempt_id = self.attempt_id_for_epoch(sandbox_id=sandbox_id, lease_epoch=1)
        policy_payload = asdict(policy)
        normalized_configuration_payload = {
            "compose_project": compose_project,
            "workspace_path": workspace_path,
            **configuration_payload,
        }
        self._validate_workload_authority(
            workload=workload,
            configuration_payload=normalized_configuration_payload,
        )
        run = RunRecord(
            run_id=run_id,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            policy_snapshot_id=f"sandbox-policy:{sandbox_id}",
            policy_digest=self._sha256_digest(policy_payload),
            configuration_snapshot_id=f"sandbox-config:{sandbox_id}",
            configuration_digest=self._sha256_digest(normalized_configuration_payload),
            creation_timestamp=creation_timestamp,
            admission_decision_receipt_ref=admission_decision_receipt_ref,
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=attempt_id,
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[admission_decision_receipt_ref],
            configuration_payload=normalized_configuration_payload,
            configuration_source_refs=[admission_decision_receipt_ref],
        )
        attempt = AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=self._starting_snapshot_ref(
                sandbox_id=sandbox_id,
                lifecycle_state="starting",
                snapshot_suffix="initial",
            ),
            start_timestamp=creation_timestamp,
        )
        await self.repository.save_run_record(record=run)
        await self.repository.save_attempt_record(record=attempt)
        return run, attempt

    @staticmethod
    def _validate_workload_authority(
        *,
        workload: WorkloadRecord,
        configuration_payload: dict[str, object],
    ) -> None:
        if workload.output_contract_ref != CONTROL_PLANE_RUN_OUTPUT_CONTRACT_REF:
            raise SandboxControlPlaneExecutionError(
                "sandbox workload output_contract_ref must target ControlPlane run authority"
            )
        tech_stack = str(configuration_payload.get("tech_stack") or "").strip().lower()
        if not tech_stack:
            return
        expected = sandbox_runtime_workload_for_tech_stack(tech_stack)
        if workload.workload_id != expected.workload_id or workload.workload_version != expected.workload_version:
            raise SandboxControlPlaneExecutionError(
                "sandbox workload authority mismatch for tech_stack: "
                f"expected={expected.workload_id}@{expected.workload_version} "
                f"got={workload.workload_id}@{workload.workload_version}"
            )

    async def mark_waiting_on_observation(
        self,
        *,
        run_id: str,
        sandbox_id: str,
        observed_at: str,
    ) -> tuple[RunRecord, AttemptRecord]:
        run, attempt = await self._require_current_execution(run_id=run_id)
        if run.lifecycle_state is RunState.WAITING_ON_OBSERVATION and attempt.attempt_state is AttemptState.WAITING:
            return run, attempt
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.WAITING_ON_OBSERVATION)
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.WAITING)
        updated_attempt = attempt.model_copy(update={"attempt_state": AttemptState.WAITING})
        updated_run = run.model_copy(update={"lifecycle_state": RunState.WAITING_ON_OBSERVATION})
        await self.repository.save_attempt_record(record=updated_attempt)
        await self.repository.save_run_record(record=updated_run)
        return updated_run, updated_attempt

    async def resume_waiting_execution(
        self,
        *,
        run_id: str,
    ) -> tuple[RunRecord, AttemptRecord]:
        run, attempt = await self._require_current_execution(run_id=run_id)
        if run.lifecycle_state is RunState.EXECUTING and attempt.attempt_state is AttemptState.EXECUTING:
            return run, attempt
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
        updated_attempt = attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
        updated_run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING})
        await self.repository.save_attempt_record(record=updated_attempt)
        await self.repository.save_run_record(record=updated_run)
        return updated_run, updated_attempt

    async def mark_waiting_on_resource(
        self,
        *,
        run_id: str,
        observed_at: str,
    ) -> tuple[RunRecord, AttemptRecord]:
        run, attempt = await self._require_current_execution(run_id=run_id)
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.WAITING_ON_RESOURCE)
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.INTERRUPTED)
        failure_plane, failure_classification = infer_failure_taxonomy(failure_classification_basis="lease_expired")
        updated_attempt = attempt.model_copy(
            update={
                "attempt_state": AttemptState.INTERRUPTED,
                "end_timestamp": observed_at,
                "side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                "failure_class": "lease_expired",
                "failure_plane": failure_plane,
                "failure_classification": failure_classification,
            }
        )
        updated_run = run.model_copy(update={"lifecycle_state": RunState.WAITING_ON_RESOURCE})
        await self.repository.save_attempt_record(record=updated_attempt)
        await self.repository.save_run_record(record=updated_run)
        return updated_run, updated_attempt

    async def start_new_attempt_after_reacquire(
        self,
        *,
        sandbox_id: str,
        run_id: str,
        lease_epoch: int,
        observed_at: str,
        policy_version: str,
        rationale_ref: str,
    ) -> tuple[RunRecord, AttemptRecord, RecoveryDecisionRecord | None]:
        run = await self._require_run(run_id=run_id)
        attempts = await self.repository.list_attempt_records(run_id=run_id)
        if not attempts:
            raise SandboxControlPlaneExecutionError(f"no prior attempt exists for run {run_id}")
        last_attempt = attempts[-1]
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        next_attempt_id = self.attempt_id_for_epoch(sandbox_id=sandbox_id, lease_epoch=lease_epoch)
        decision = None
        if self.publication is not None:
            target_checkpoint_id, checkpoint_acceptance, required_precondition_refs = await self._checkpoint_context(
                attempt_id=last_attempt.attempt_id
            )
            authorized_next_action = RecoveryActionClass.START_NEW_ATTEMPT
            if target_checkpoint_id is not None and checkpoint_acceptance is not None:
                authorized_next_action = RecoveryActionClass.RESUME_FROM_CHECKPOINT
            decision = await self.publication.publish_recovery_decision(
                decision_id=f"sandbox-recovery:{run_id}:reacquire:{lease_epoch:08d}",
                run_id=run_id,
                failed_attempt_id=last_attempt.attempt_id,
                failure_classification_basis="lease_expired",
                side_effect_boundary_class=SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                recovery_policy_ref=f"sandbox_lifecycle_policy:{policy_version}",
                authorized_next_action=authorized_next_action,
                rationale_ref=rationale_ref,
                new_attempt_id=next_attempt_id,
                required_precondition_refs=required_precondition_refs,
                target_checkpoint_id=target_checkpoint_id if checkpoint_acceptance is not None else None,
                checkpoint_acceptance=checkpoint_acceptance,
            )
            last_attempt = last_attempt.model_copy(update={"recovery_decision_id": decision.decision_id})
            await self.repository.save_attempt_record(record=last_attempt)
        next_attempt = AttemptRecord(
            attempt_id=next_attempt_id,
            run_id=run_id,
            attempt_ordinal=lease_epoch,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=self._starting_snapshot_ref(
                sandbox_id=sandbox_id,
                lifecycle_state="active",
                snapshot_suffix=f"lease_epoch_{lease_epoch}",
            ),
            start_timestamp=observed_at,
        )
        updated_run = run.model_copy(update={"lifecycle_state": RunState.EXECUTING, "current_attempt_id": next_attempt_id})
        await self.repository.save_attempt_record(record=next_attempt)
        await self.repository.save_run_record(record=updated_run)
        return updated_run, next_attempt, decision

    async def finalize_terminal_execution(
        self,
        *,
        run_id: str,
        observed_at: str,
        terminal_reason: TerminalReason,
        policy_version: str,
        final_truth_record_id: str | None,
        rationale_ref: str,
        recovery_rationale_ref: str | None = None,
    ) -> tuple[RunRecord, AttemptRecord | None, RecoveryDecisionRecord | None]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._current_attempt(run=run)
        if run.lifecycle_state in {RunState.COMPLETED, RunState.FAILED_TERMINAL, RunState.CANCELLED}:
            return run, attempt, None

        target_run_state = self._terminal_run_state(terminal_reason)
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=target_run_state)
        updated_attempt = attempt
        decision = None
        if attempt is not None and attempt.attempt_state not in {
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
            AttemptState.COMPLETED,
            AttemptState.ABANDONED,
        }:
            target_attempt_state, side_effect_boundary_class, failure_class = self._attempt_terminal_projection(
                terminal_reason
            )
            validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=target_attempt_state)
            failure_basis = failure_class or terminal_reason.value
            failure_plane, failure_classification = infer_failure_taxonomy(
                failure_classification_basis=failure_basis
            )
            updated_attempt = attempt.model_copy(
                update={
                    "attempt_state": target_attempt_state,
                    "end_timestamp": observed_at,
                    "side_effect_boundary_class": side_effect_boundary_class,
                    "failure_class": failure_class,
                    "failure_plane": failure_plane,
                    "failure_classification": failure_classification,
                }
            )
            await self.repository.save_attempt_record(record=updated_attempt)
            if (
                self.publication is not None
                and side_effect_boundary_class is not None
                and terminal_reason is not TerminalReason.CANCELED
            ):
                decision = await self.publication.publish_recovery_decision(
                    decision_id=f"sandbox-recovery:{run_id}:terminal:{terminal_reason.value}:{observed_at}",
                    run_id=run_id,
                    failed_attempt_id=attempt.attempt_id,
                    failure_classification_basis=failure_basis,
                    side_effect_boundary_class=side_effect_boundary_class,
                    recovery_policy_ref=f"sandbox_lifecycle_policy:{policy_version}",
                    authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
                    rationale_ref=recovery_rationale_ref or rationale_ref,
                )
                updated_attempt = updated_attempt.model_copy(
                    update={
                        "recovery_decision_id": decision.decision_id,
                        "failure_plane": decision.failure_plane,
                        "failure_classification": decision.failure_classification,
                    }
                )
                await self.repository.save_attempt_record(record=updated_attempt)

        updated_run = run.model_copy(
            update={
                "lifecycle_state": target_run_state,
                "final_truth_record_id": final_truth_record_id,
            }
        )
        await self.repository.save_run_record(record=updated_run)
        return updated_run, updated_attempt, decision

    @staticmethod
    def attempt_id_for_epoch(*, sandbox_id: str, lease_epoch: int) -> str:
        return f"sandbox-attempt:{sandbox_id}:{lease_epoch:08d}"

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.repository.get_run_record(run_id=run_id)
        if run is None:
            raise SandboxControlPlaneExecutionError(f"control-plane run not found for {run_id}")
        return run

    async def _current_attempt(self, *, run: RunRecord) -> AttemptRecord | None:
        if run.current_attempt_id is None:
            attempts = await self.repository.list_attempt_records(run_id=run.run_id)
            return attempts[-1] if attempts else None
        return await self.repository.get_attempt_record(attempt_id=run.current_attempt_id)

    async def _checkpoint_context(
        self,
        *,
        attempt_id: str,
    ) -> tuple[str | None, CheckpointAcceptanceRecord | None, list[str]]:
        if self.publication is None:
            return None, None, []
        checkpoints = await self.publication.repository.list_checkpoints(parent_ref=attempt_id)
        if not checkpoints:
            return None, None, []
        latest = checkpoints[-1]
        refs = [latest.checkpoint_id]
        acceptance = await self.publication.repository.get_checkpoint_acceptance(checkpoint_id=latest.checkpoint_id)
        if acceptance is not None:
            refs.append(acceptance.acceptance_id)
        return latest.checkpoint_id, acceptance, refs

    async def _require_current_execution(self, *, run_id: str) -> tuple[RunRecord, AttemptRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._current_attempt(run=run)
        if attempt is None:
            raise SandboxControlPlaneExecutionError(f"no current attempt exists for run {run_id}")
        return run, attempt

    @staticmethod
    def _terminal_run_state(reason: TerminalReason) -> RunState:
        if reason is TerminalReason.SUCCESS:
            return RunState.COMPLETED
        if reason is TerminalReason.CANCELED:
            return RunState.CANCELLED
        if reason is TerminalReason.LEASE_EXPIRED:
            return RunState.CANCELLED
        return RunState.FAILED_TERMINAL

    @staticmethod
    def _attempt_terminal_projection(
        reason: TerminalReason,
    ) -> tuple[AttemptState, SideEffectBoundaryClass | None, str | None]:
        if reason is TerminalReason.SUCCESS:
            return AttemptState.COMPLETED, None, None
        if reason is TerminalReason.CANCELED:
            return AttemptState.ABANDONED, None, None
        if reason in {TerminalReason.CREATE_FAILED, TerminalReason.START_FAILED}:
            return AttemptState.FAILED, SideEffectBoundaryClass.PRE_EFFECT_FAILURE, reason.value
        if reason is TerminalReason.LOST_RUNTIME:
            return AttemptState.INTERRUPTED, SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN, reason.value
        if reason is TerminalReason.LEASE_EXPIRED:
            return AttemptState.INTERRUPTED, SideEffectBoundaryClass.POST_EFFECT_OBSERVED, reason.value
        return AttemptState.FAILED, SideEffectBoundaryClass.POST_EFFECT_OBSERVED, reason.value

    @staticmethod
    def _starting_snapshot_ref(
        *,
        sandbox_id: str,
        lifecycle_state: str,
        snapshot_suffix: str,
    ) -> str:
        return f"sandbox-lifecycle:{sandbox_id}:{lifecycle_state}:{snapshot_suffix}"

    @staticmethod
    def _sha256_digest(payload: dict[str, object]) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return f"sha256:{hashlib.sha256(blob.encode('utf-8')).hexdigest()}"


__all__ = [
    "SandboxControlPlaneExecutionError",
    "SandboxControlPlaneExecutionService",
]
