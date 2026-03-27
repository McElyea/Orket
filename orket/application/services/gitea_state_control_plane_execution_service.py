from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, FinalTruthRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.runtime_paths import resolve_control_plane_db_path


class GiteaStateControlPlaneExecutionError(ValueError):
    """Raised when Gitea worker execution authority cannot be published truthfully."""


class GiteaStateControlPlaneExecutionService:
    """Publishes lease-backed Gitea worker execution into first-class control-plane records."""

    WORKLOAD_ID = "gitea-state-worker-card-execution"
    WORKLOAD_VERSION = "gitea_state_worker.v1"

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def begin_claimed_execution(
        self,
        *,
        card_id: str,
        worker_id: str,
        from_state: str,
        success_state: str,
        failure_state: str,
        lease_observation: Mapping[str, object],
    ) -> tuple[RunRecord, AttemptRecord]:
        lease_epoch = self._lease_epoch(lease_observation)
        run_id = self.run_id_for(card_id=card_id, lease_epoch=lease_epoch)
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is not None:
            attempt = await self.execution_repository.get_attempt_record(
                attempt_id=self.attempt_id_for(run_id=run_id)
            )
            if attempt is None:
                raise GiteaStateControlPlaneExecutionError(f"gitea run missing attempt: {run_id}")
            return existing_run, attempt

        creation_timestamp = str(self._lease_payload(lease_observation).get("acquired_at") or self._utc_now())
        policy_payload = {
            "success_state": str(success_state),
            "failure_state": str(failure_state),
            "lease_epoch": lease_epoch,
        }
        configuration_payload = {
            "card_id": str(card_id),
            "worker_id": str(worker_id),
            "from_state": str(from_state),
            "success_state": str(success_state),
            "failure_state": str(failure_state),
            "lease_observation": dict(lease_observation),
        }
        run = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD_ID,
            workload_version=self.WORKLOAD_VERSION,
            policy_snapshot_id=f"gitea-state-worker-policy:{card_id}",
            policy_digest=snapshot_digest(policy_payload),
            configuration_snapshot_id=f"gitea-state-worker-config:{run_id}",
            configuration_digest=snapshot_digest(configuration_payload),
            creation_timestamp=creation_timestamp,
            admission_decision_receipt_ref=self.lease_observation_ref(card_id=card_id, lease_observation=lease_observation),
            namespace_scope=self.namespace_scope_for(card_id=card_id),
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=self.attempt_id_for(run_id=run_id),
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[run.admission_decision_receipt_ref],
            configuration_payload=configuration_payload,
            configuration_source_refs=[run.admission_decision_receipt_ref],
        )
        attempt = AttemptRecord(
            attempt_id=self.attempt_id_for(run_id=run_id),
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=self.snapshot_ref(card_id=card_id, from_state=from_state, lease_observation=lease_observation),
            start_timestamp=creation_timestamp,
        )
        await self.execution_repository.save_run_record(record=run)
        await self.execution_repository.save_attempt_record(record=attempt)
        return run, attempt

    async def publish_claim_transition(
        self,
        *,
        run_id: str,
        attempt_id: str,
        card_id: str,
        from_state: str,
        to_state: str,
    ) -> tuple[StepRecord, EffectJournalEntryRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=attempt_id)
        step_id = self.step_id_for(run_id=run_id, stage="claim")
        existing_step = await self.execution_repository.get_step_record(step_id=step_id)
        if existing_step is None:
            existing_step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=step_id,
                    attempt_id=attempt.attempt_id,
                    step_kind="gitea_state_transition",
                    namespace_scope=run.namespace_scope,
                    input_ref=attempt.starting_state_snapshot_ref,
                    output_ref=self.transition_result_ref(
                        card_id=card_id,
                        lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                        from_state=from_state,
                        to_state=to_state,
                    ),
                    capability_used=CapabilityClass.EXTERNAL_MUTATION,
                    resources_touched=self._resources_touched(card_id=card_id),
                    observed_result_classification="state_transition_succeeded",
                    receipt_refs=[
                        attempt.starting_state_snapshot_ref,
                        self.transition_result_ref(
                            card_id=card_id,
                            lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                            from_state=from_state,
                            to_state=to_state,
                        ),
                    ],
                    closure_classification="step_completed",
                )
            )
        effect = await self._ensure_effect(
            run=run,
            attempt=attempt,
            step=existing_step,
            stage="claim",
            card_id=card_id,
        )
        return existing_step, effect

    async def publish_release_transition_and_finalize(
        self,
        *,
        run_id: str,
        attempt_id: str,
        card_id: str,
        final_state: str,
        error: str | None,
        success_state: str,
    ) -> tuple[RunRecord, AttemptRecord, StepRecord, EffectJournalEntryRecord, FinalTruthRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=attempt_id)
        existing_truth = await self.publication.repository.get_final_truth(run_id=run_id)
        existing_step = await self.execution_repository.get_step_record(step_id=self.step_id_for(run_id=run_id, stage="finalize"))
        if existing_truth is not None and existing_step is not None:
            return run, attempt, existing_step, await self._require_effect(run_id=run_id, stage="finalize"), existing_truth

        step = existing_step
        if step is None:
            claim_step = await self.execution_repository.get_step_record(step_id=self.step_id_for(run_id=run_id, stage="claim"))
            step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=self.step_id_for(run_id=run_id, stage="finalize"),
                    attempt_id=attempt.attempt_id,
                    step_kind="gitea_state_transition",
                    namespace_scope=run.namespace_scope,
                    input_ref=claim_step.output_ref if claim_step is not None and claim_step.output_ref else run.admission_decision_receipt_ref,
                    output_ref=self.transition_result_ref(
                        card_id=card_id,
                        lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                        from_state="in_progress",
                        to_state=final_state,
                    ),
                    capability_used=CapabilityClass.EXTERNAL_MUTATION,
                    resources_touched=self._resources_touched(card_id=card_id),
                    observed_result_classification="state_transition_succeeded",
                    receipt_refs=[
                        self.transition_result_ref(
                            card_id=card_id,
                            lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                            from_state="in_progress",
                            to_state=final_state,
                        )
                    ],
                    closure_classification="step_completed",
                )
            )
        effect = await self._ensure_effect(
            run=run,
            attempt=attempt,
            step=step,
            stage="finalize",
            card_id=card_id,
        )

        lease_expired = str(error or "").strip().upper() == "E_LEASE_EXPIRED"
        if existing_truth is None:
            if not error and final_state == str(success_state).strip():
                validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.COMPLETED)
                validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.COMPLETED)
                attempt = attempt.model_copy(
                    update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": self._utc_now()}
                )
                run = run.model_copy(update={"lifecycle_state": RunState.COMPLETED})
                truth = await self.publication.publish_final_truth(
                    final_truth_record_id=f"gitea-state-final-truth:{run.run_id}",
                    run_id=run.run_id,
                    result_class=ResultClass.SUCCESS,
                    completion_classification=CompletionClassification.SATISFIED,
                    evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
                    residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
                    degradation_classification=DegradationClassification.NONE,
                    closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
                    authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
                    authoritative_result_ref=step.output_ref,
                )
            else:
                target_attempt_state = AttemptState.INTERRUPTED if lease_expired else AttemptState.FAILED
                failure_class = "lease_expired" if lease_expired else "gitea_state_worker_failure"
                closure_basis = (
                    ClosureBasisClassification.POLICY_TERMINAL_STOP
                    if lease_expired
                    else ClosureBasisClassification.NORMAL_EXECUTION
                )
                result_class = ResultClass.BLOCKED if lease_expired else ResultClass.FAILED
                validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=target_attempt_state)
                validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.FAILED_TERMINAL)
                attempt = attempt.model_copy(
                    update={
                        "attempt_state": target_attempt_state,
                        "end_timestamp": self._utc_now(),
                        "side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                        "failure_class": failure_class,
                    }
                )
                decision = await self.publication.publish_recovery_decision(
                    decision_id=f"gitea-state-recovery:{run.run_id}:{failure_class}",
                    run_id=run.run_id,
                    failed_attempt_id=attempt.attempt_id,
                    failure_classification_basis=failure_class,
                    side_effect_boundary_class=SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                    recovery_policy_ref="gitea_state_worker_terminal_policy.v1",
                    authorized_next_action=RecoveryActionClass.TERMINATE_RUN,
                    rationale_ref=effect.journal_entry_id,
                )
                attempt = attempt.model_copy(update={"recovery_decision_id": decision.decision_id, "failure_plane": decision.failure_plane, "failure_classification": decision.failure_classification})
                run = run.model_copy(update={"lifecycle_state": RunState.FAILED_TERMINAL})
                truth = await self.publication.publish_final_truth(
                    final_truth_record_id=f"gitea-state-final-truth:{run.run_id}",
                    run_id=run.run_id,
                    result_class=result_class,
                    completion_classification=CompletionClassification.UNSATISFIED,
                    evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
                    residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
                    degradation_classification=DegradationClassification.NONE,
                    closure_basis=closure_basis,
                    authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
                    authoritative_result_ref=step.output_ref,
                )
            run = run.model_copy(update={"final_truth_record_id": truth.final_truth_record_id})
            await self.execution_repository.save_attempt_record(record=attempt)
            await self.execution_repository.save_run_record(record=run)
            return run, attempt, step, effect, truth

        return run, attempt, step, effect, existing_truth

    @staticmethod
    def run_id_for(*, card_id: str, lease_epoch: int) -> str:
        return f"gitea-state-run:{str(card_id).strip()}:lease_epoch:{int(lease_epoch):08d}"

    @staticmethod
    def attempt_id_for(*, run_id: str) -> str:
        return f"{run_id}:attempt:0001"

    @staticmethod
    def step_id_for(*, run_id: str, stage: str) -> str:
        return f"{run_id}:step:{str(stage).strip()}"

    @staticmethod
    def effect_id_for(*, run_id: str, stage: str) -> str:
        return f"gitea-state-effect:{run_id}:{str(stage).strip()}"

    @staticmethod
    def namespace_scope_for(*, card_id: str) -> str:
        return f"issue:{str(card_id).strip()}"

    @classmethod
    def lease_epoch_for_run(cls, *, run_id: str) -> int:
        marker = ":lease_epoch:"
        if marker not in run_id:
            raise GiteaStateControlPlaneExecutionError(f"run_id missing lease epoch: {run_id}")
        return int(run_id.rsplit(marker, 1)[-1])

    @classmethod
    def lease_observation_ref(cls, *, card_id: str, lease_observation: Mapping[str, object]) -> str:
        version = lease_observation.get("version")
        if version is not None:
            return f"gitea-card-snapshot:{str(card_id).strip()}:version:{int(version)}"
        return f"gitea-card-lease-observation:{str(card_id).strip()}:epoch:{cls._lease_epoch(lease_observation):08d}"

    @classmethod
    def snapshot_ref(cls, *, card_id: str, from_state: str, lease_observation: Mapping[str, object]) -> str:
        observation_ref = cls.lease_observation_ref(card_id=card_id, lease_observation=lease_observation)
        return f"{observation_ref}:state:{str(from_state).strip() or 'ready'}"

    @staticmethod
    def transition_result_ref(*, card_id: str, lease_epoch: int, from_state: str, to_state: str) -> str:
        return (
            f"gitea-card-transition:{str(card_id).strip()}"
            f":lease_epoch:{int(lease_epoch):08d}"
            f":{str(from_state).strip() or 'unknown'}->{str(to_state).strip() or 'unknown'}"
        )

    async def _ensure_effect(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        step: StepRecord,
        stage: str,
        card_id: str,
    ) -> EffectJournalEntryRecord:
        existing = await self._existing_effect(run_id=run.run_id, stage=stage)
        if existing is not None:
            return existing
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=f"gitea-state-journal:{run.run_id}:{stage}",
            effect_id=self.effect_id_for(run_id=run.run_id, stage=stage),
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=run.admission_decision_receipt_ref,
            publication_timestamp=self._utc_now(),
            intended_target_ref=f"gitea-card:{str(card_id).strip()}",
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or run.admission_decision_receipt_ref,
        )

    async def _existing_effect(self, *, run_id: str, stage: str) -> EffectJournalEntryRecord | None:
        effect_id = self.effect_id_for(run_id=run_id, stage=stage)
        entries = await self.publication.repository.list_effect_journal_entries(run_id=run_id)
        for entry in entries:
            if entry.effect_id == effect_id:
                return entry
        return None

    async def _require_effect(self, *, run_id: str, stage: str) -> EffectJournalEntryRecord:
        effect = await self._existing_effect(run_id=run_id, stage=stage)
        if effect is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea run missing effect journal entry: {run_id}:{stage}")
        return effect

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea worker run not found: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str) -> AttemptRecord:
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if attempt is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea worker attempt not found: {attempt_id}")
        return attempt

    @staticmethod
    def _resources_touched(*, card_id: str) -> list[str]:
        normalized_card_id = str(card_id).strip()
        namespace_scope = GiteaStateControlPlaneExecutionService.namespace_scope_for(card_id=normalized_card_id)
        return [f"gitea-card:{normalized_card_id}", f"issue:{normalized_card_id}", f"namespace:{namespace_scope}"]

    @staticmethod
    def _lease_payload(lease_observation: Mapping[str, object]) -> Mapping[str, object]:
        nested = lease_observation.get("lease")
        return nested if isinstance(nested, Mapping) else lease_observation

    @classmethod
    def _lease_epoch(cls, lease_observation: Mapping[str, object]) -> int:
        payload = cls._lease_payload(lease_observation)
        raw = payload.get("epoch")
        if raw is None:
            raw = lease_observation.get("lease_epoch")
        try:
            return int(raw)
        except (TypeError, ValueError) as exc:
            raise GiteaStateControlPlaneExecutionError("gitea worker execution publication requires lease epoch") from exc

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

def build_gitea_state_control_plane_execution_service(db_path: str | Path | None = None) -> GiteaStateControlPlaneExecutionService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneExecutionService(
        execution_repository=AsyncControlPlaneExecutionRepository(resolved_db_path),
        publication=publication,
    )

__all__ = [
    "GiteaStateControlPlaneExecutionError",
    "GiteaStateControlPlaneExecutionService",
    "build_gitea_state_control_plane_execution_service",
]
