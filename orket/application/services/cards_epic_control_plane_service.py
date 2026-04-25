from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    RunRecord,
    StepRecord,
    WorkloadRecord,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    validate_attempt_state_transition,
    validate_run_state_transition,
)
from orket.utils import sanitize_name


class CardsEpicControlPlaneError(ValueError):
    """Raised when cards-epic control-plane truth cannot be published honestly."""


class CardsEpicControlPlaneService:
    """Publishes invocation-scoped run, attempt, and start-step authority for top-level cards epic execution."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication

    async def begin_execution(
        self,
        *,
        session_id: str,
        build_id: str,
        epic_name: str,
        department: str,
        workload: WorkloadRecord,
        resume_mode: bool,
        target_issue_id: str | None,
    ) -> tuple[RunRecord, AttemptRecord, StepRecord, CheckpointRecord, CheckpointAcceptanceRecord]:
        created_at = self._utc_now()
        run_id = self.run_id_for(session_id=session_id, build_id=build_id, created_at=created_at)
        attempt_id = self.attempt_id_for(run_id=run_id)
        admission_ref = self.admission_ref_for(run_id=run_id)
        policy_payload = {
            "entry_mode": "cards_epic_run",
            "resume_mode": bool(resume_mode),
            "target_issue_id": str(target_issue_id or ""),
        }
        configuration_payload = {
            "session_id": str(session_id),
            "build_id": str(build_id),
            "epic_name": str(epic_name),
            "department": str(department),
            "workload_id": str(workload.workload_id),
            "workload_version": str(workload.workload_version),
            "resume_mode": bool(resume_mode),
            "target_issue_id": str(target_issue_id or ""),
        }
        run = RunRecord(
            run_id=run_id,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            policy_snapshot_id=f"cards-epic-policy:{run_id}",
            policy_digest=snapshot_digest(policy_payload),
            configuration_snapshot_id=f"cards-epic-config:{run_id}",
            configuration_digest=snapshot_digest(configuration_payload),
            creation_timestamp=created_at,
            admission_decision_receipt_ref=admission_ref,
            lifecycle_state=RunState.ADMISSION_PENDING,
            current_attempt_id=attempt_id,
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[admission_ref],
            configuration_payload=configuration_payload,
            configuration_source_refs=[admission_ref],
        )
        attempt = AttemptRecord(
            attempt_id=attempt_id,
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.CREATED,
            starting_state_snapshot_ref=admission_ref,
            start_timestamp=created_at,
        )
        await self.execution_repository.save_run_record(record=run)
        await self.execution_repository.save_attempt_record(record=attempt)

        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.ADMITTED)
        run = await self.execution_repository.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.ADMITTED}))
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=RunState.EXECUTING)
        run = await self.execution_repository.save_run_record(record=run.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
        attempt = await self.execution_repository.save_attempt_record(
            record=attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING})
        )
        step = await self.execution_repository.save_step_record(
            record=StepRecord(
                step_id=self.start_step_id_for(run_id=run_id),
                attempt_id=attempt.attempt_id,
                step_kind="cards_epic_session_start",
                input_ref=admission_ref,
                output_ref=admission_ref,
                capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                resources_touched=[
                    f"epic:{sanitize_name(str(epic_name))}",
                    f"build:{sanitize_name(str(build_id))}",
                ],
                observed_result_classification="cards_epic_run_started",
                receipt_refs=[admission_ref],
                closure_classification="step_completed",
            )
        )
        start_effect = await self._ensure_effect(
            run=run,
            attempt=attempt,
            step=step,
            stage="start",
        )
        checkpoint = await self.publication.publish_checkpoint(
            checkpoint=CheckpointRecord(
                checkpoint_id=self.checkpoint_id_for(attempt_id=attempt.attempt_id),
                parent_ref=attempt.attempt_id,
                creation_timestamp=created_at,
                state_snapshot_ref=run.configuration_snapshot_id,
                resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
                invalidation_conditions=[
                    "cards_epic_resume_mode_drift",
                    "cards_epic_target_issue_drift",
                    "cards_epic_build_drift",
                ],
                dependent_resource_ids=step.resources_touched,
                dependent_effect_refs=[],
                policy_digest=run.policy_digest,
                integrity_verification_ref=self.checkpoint_integrity_ref(run=run),
            )
        )
        checkpoint_acceptance = await self.publication.accept_checkpoint(
            acceptance_id=self.checkpoint_acceptance_id_for(attempt_id=attempt.attempt_id),
            checkpoint=checkpoint,
            supervisor_authority_ref=f"cards-epic-supervisor:{run.run_id}",
            decision_timestamp=checkpoint.creation_timestamp,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
            journal_entries=[start_effect],
        )
        return run, attempt, step, checkpoint, checkpoint_acceptance

    async def finalize_execution(
        self,
        *,
        run_id: str,
        session_status: str,
        failure_reason: str | None = None,
    ) -> tuple[RunRecord, AttemptRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=run.current_attempt_id)
        status = str(session_status or "").strip().lower()
        ended_at = self._utc_now()
        closeout_ref = self.closeout_ref_for(run_id=run_id, session_status=status)

        if status == "done":
            next_run_state = RunState.COMPLETED
            next_attempt_state = AttemptState.COMPLETED
            attempt_update = {"attempt_state": next_attempt_state, "end_timestamp": ended_at}
        elif status in {"terminal_failure", "failed"}:
            next_run_state = RunState.FAILED_TERMINAL
            next_attempt_state = AttemptState.FAILED
            attempt_update = {
                "attempt_state": next_attempt_state,
                "end_timestamp": ended_at,
                "failure_class": str(failure_reason or status)[:200],
            }
        elif status == "incomplete":
            next_run_state = RunState.WAITING_ON_OBSERVATION
            next_attempt_state = AttemptState.WAITING
            attempt_update = {"attempt_state": next_attempt_state}
        else:
            raise CardsEpicControlPlaneError(f"unsupported cards epic session_status={session_status!r}")

        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=next_attempt_state)
        attempt = await self.execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_run_state)
        run_update: dict[str, object] = {"lifecycle_state": next_run_state}
        if next_run_state in {RunState.COMPLETED, RunState.FAILED_TERMINAL}:
            closeout_step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=self.closeout_step_id_for(run_id=run_id),
                    attempt_id=attempt.attempt_id,
                    step_kind="cards_epic_session_closeout",
                    input_ref=self.start_step_id_for(run_id=run_id),
                    output_ref=closeout_ref,
                    capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                    resources_touched=[],
                    observed_result_classification=f"cards_epic_session_{status}",
                    receipt_refs=[closeout_ref],
                    closure_classification="step_completed",
                )
            )
            await self._ensure_effect(
                run=run,
                attempt=attempt,
                step=closeout_step,
                stage="closeout",
            )
            truth = await self.publication.publish_final_truth(
                final_truth_record_id=self.final_truth_id_for(run_id=run_id),
                run_id=run_id,
                result_class=(ResultClass.SUCCESS if status == "done" else ResultClass.FAILED),
                completion_classification=(
                    CompletionClassification.SATISFIED
                    if status == "done"
                    else CompletionClassification.UNSATISFIED
                ),
                evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
                residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
                degradation_classification=DegradationClassification.NONE,
                closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
                authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
                authoritative_result_ref=closeout_ref,
            )
            run_update["final_truth_record_id"] = truth.final_truth_record_id
        else:
            closeout_step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=self.closeout_step_id_for(run_id=run_id),
                    attempt_id=attempt.attempt_id,
                    step_kind="cards_epic_session_wait",
                    input_ref=self.start_step_id_for(run_id=run_id),
                    output_ref=closeout_ref,
                    capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                    resources_touched=[],
                    observed_result_classification=f"cards_epic_session_{status}",
                    receipt_refs=[closeout_ref],
                    closure_classification="step_completed",
                )
            )
            await self._ensure_effect(
                run=run,
                attempt=attempt,
                step=closeout_step,
                stage="wait",
            )
        run = await self.execution_repository.save_run_record(record=run.model_copy(update=run_update))
        return run, attempt

    @staticmethod
    def run_id_for(*, session_id: str, build_id: str, created_at: str) -> str:
        timestamp = CardsEpicControlPlaneService._timestamp_token(created_at=created_at)
        return (
            "cards-epic-run:"
            f"{sanitize_name(str(session_id))}:"
            f"{sanitize_name(str(build_id))}:"
            f"{timestamp}"
        )

    @staticmethod
    def attempt_id_for(*, run_id: str) -> str:
        return f"{run_id}:attempt:0001"

    @staticmethod
    def admission_ref_for(*, run_id: str) -> str:
        return f"{run_id}:admission"

    @staticmethod
    def start_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:start"

    @staticmethod
    def closeout_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:closeout"

    @staticmethod
    def closeout_ref_for(*, run_id: str, session_status: str) -> str:
        return f"{run_id}:closeout:{sanitize_name(str(session_status or 'unknown'))}"

    @staticmethod
    def final_truth_id_for(*, run_id: str) -> str:
        return f"{run_id}:final_truth"

    @staticmethod
    def checkpoint_id_for(*, attempt_id: str) -> str:
        return f"cards-epic-checkpoint:{attempt_id}"

    @staticmethod
    def checkpoint_acceptance_id_for(*, attempt_id: str) -> str:
        return f"cards-epic-checkpoint-acceptance:{attempt_id}"

    @staticmethod
    def effect_id_for(*, run_id: str, stage: str) -> str:
        return f"cards-epic-effect:{run_id}:{sanitize_name(str(stage or 'unknown'))}"

    @staticmethod
    def journal_entry_id_for(*, run_id: str, stage: str) -> str:
        return f"cards-epic-journal:{run_id}:{sanitize_name(str(stage or 'unknown'))}"

    @staticmethod
    def checkpoint_integrity_ref(*, run: RunRecord) -> str:
        raw = json.dumps(
            {
                "run_id": run.run_id,
                "policy_digest": run.policy_digest,
                "configuration_digest": run.configuration_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        return f"cards-epic-checkpoint-integrity:sha256:{hashlib.sha256(raw).hexdigest()}"

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise CardsEpicControlPlaneError(f"cards epic control-plane run missing: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str | None) -> AttemptRecord:
        normalized_attempt_id = str(attempt_id or "").strip()
        if not normalized_attempt_id:
            raise CardsEpicControlPlaneError("cards epic control-plane run is missing current_attempt_id")
        attempt = await self.execution_repository.get_attempt_record(attempt_id=normalized_attempt_id)
        if attempt is None:
            raise CardsEpicControlPlaneError(f"cards epic control-plane attempt missing: {normalized_attempt_id}")
        return attempt

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _timestamp_token(*, created_at: str) -> str:
        normalized = str(created_at or "").strip()
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        parsed = datetime.fromisoformat(normalized)
        return parsed.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")

    async def _ensure_effect(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        step: StepRecord,
        stage: str,
    ) -> EffectJournalEntryRecord:
        effect_id = self.effect_id_for(run_id=run.run_id, stage=stage)
        existing = await self.publication.repository.list_effect_journal_entries(run_id=run.run_id)
        for entry in existing:
            if entry.effect_id == effect_id:
                return entry
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=self.journal_entry_id_for(run_id=run.run_id, stage=stage),
            effect_id=effect_id,
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=run.admission_decision_receipt_ref,
            publication_timestamp=self._utc_now(),
            intended_target_ref=f"cards-epic-run:{run.run_id}:lifecycle",
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or run.admission_decision_receipt_ref,
        )


__all__ = [
    "CardsEpicControlPlaneError",
    "CardsEpicControlPlaneService",
]
