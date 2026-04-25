from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.review.control_plane_projection import REVIEW_CONTROL_PLANE_PROJECTION_SOURCE
from orket.application.review.models import ReviewSnapshot
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.application.services.control_plane_workload_catalog import REVIEW_RUN_WORKLOAD
from orket.core.contracts import (
    AttemptRecord,
    CheckpointRecord,
    RunRecord,
    StepRecord,
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
from orket.runtime_paths import resolve_control_plane_db_path


class ReviewRunControlPlaneError(ValueError):
    """Raised when review-run control-plane truth cannot be published honestly."""


class ReviewRunControlPlaneService:
    """Publishes first-class run, attempt, step, and snapshot truth for manual review runs."""

    WORKLOAD = REVIEW_RUN_WORKLOAD

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
        run_id: str,
        snapshot: ReviewSnapshot,
        resolved_policy_payload: dict[str, object],
        auth_source: str,
        model_assisted_enabled: bool,
    ) -> tuple[RunRecord, AttemptRecord, StepRecord, CheckpointRecord]:
        created_at = self._utc_now()
        attempt_id = self.attempt_id_for(run_id=run_id)
        admission_ref = self.admission_ref_for(snapshot=snapshot)
        policy_payload = {
            "resolved_policy": dict(resolved_policy_payload),
            "model_assisted_enabled": bool(model_assisted_enabled),
        }
        configuration_payload = {
            "source": str(snapshot.source),
            "repo": dict(snapshot.repo),
            "base_ref": str(snapshot.base_ref),
            "head_ref": str(snapshot.head_ref),
            "auth_source": str(auth_source),
        }
        run = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD.workload_id,
            workload_version=self.WORKLOAD.workload_version,
            policy_snapshot_id=f"review-run-policy:{run_id}",
            policy_digest=snapshot_digest(policy_payload),
            configuration_snapshot_id=f"review-run-config:{run_id}",
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
                step_kind="review_run_start",
                input_ref=admission_ref,
                output_ref=admission_ref,
                capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                resources_touched=self._resources_touched(snapshot=snapshot),
                observed_result_classification="review_run_started",
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
                    "review_snapshot_drift",
                    "review_policy_digest_drift",
                    "review_auth_source_drift",
                ],
                dependent_resource_ids=self._resources_touched(snapshot=snapshot),
                dependent_effect_refs=[],
                policy_digest=run.policy_digest,
                integrity_verification_ref=self.checkpoint_integrity_ref(run=run),
            )
        )
        await self.publication.accept_checkpoint(
            acceptance_id=self.checkpoint_acceptance_id_for(attempt_id=attempt.attempt_id),
            checkpoint=checkpoint,
            supervisor_authority_ref=f"review-run-supervisor:{run.run_id}",
            decision_timestamp=checkpoint.creation_timestamp,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
            journal_entries=[start_effect],
        )
        return run, attempt, step, checkpoint

    async def finalize_completed(self, *, run_id: str) -> tuple[RunRecord, AttemptRecord]:
        return await self._finalize(run_id=run_id, failed=False, failure_class="")

    async def finalize_failed(self, *, run_id: str, failure_class: str) -> tuple[RunRecord, AttemptRecord]:
        return await self._finalize(run_id=run_id, failed=True, failure_class=failure_class)

    async def finalize_failed_if_started(
        self,
        *,
        run_id: str,
        failure_class: str,
    ) -> tuple[RunRecord, AttemptRecord] | None:
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is None:
            return None
        return await self._finalize(run_id=run_id, failed=True, failure_class=failure_class)

    async def read_execution_summary(self, *, run_id: str) -> dict[str, object]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=run.current_attempt_id)
        step = await self.execution_repository.get_step_record(step_id=self.start_step_id_for(run_id=run_id))
        summary: dict[str, object] = {
            "projection_source": REVIEW_CONTROL_PLANE_PROJECTION_SOURCE,
            "projection_only": True,
            "run_id": run.run_id,
            "run_state": run.lifecycle_state.value,
            "workload_id": run.workload_id,
            "workload_version": run.workload_version,
            "attempt_id": attempt.attempt_id,
            "attempt_state": attempt.attempt_state.value,
            "attempt_ordinal": attempt.attempt_ordinal,
            "policy_snapshot_id": run.policy_snapshot_id,
            "configuration_snapshot_id": run.configuration_snapshot_id,
        }
        if attempt.failure_class:
            summary["failure_class"] = attempt.failure_class
        if step is not None:
            summary["step_id"] = step.step_id
            summary["step_kind"] = step.step_kind
        checkpoint = await self.publication.repository.get_checkpoint(
            checkpoint_id=self.checkpoint_id_for(attempt_id=attempt.attempt_id)
        )
        if checkpoint is not None:
            summary["checkpoint_id"] = checkpoint.checkpoint_id
            summary["checkpoint_resumability_class"] = checkpoint.resumability_class.value
            acceptance = await self.publication.repository.get_checkpoint_acceptance(
                checkpoint_id=checkpoint.checkpoint_id
            )
            if acceptance is not None:
                summary["checkpoint_acceptance_outcome"] = acceptance.outcome.value
                summary["checkpoint_acceptance_id"] = acceptance.acceptance_id
        return summary

    async def _finalize(
        self,
        *,
        run_id: str,
        failed: bool,
        failure_class: str,
    ) -> tuple[RunRecord, AttemptRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=run.current_attempt_id)
        if run.lifecycle_state in {RunState.COMPLETED, RunState.FAILED_TERMINAL}:
            return run, attempt

        ended_at = self._utc_now()
        if failed:
            next_run_state = RunState.FAILED_TERMINAL
            next_attempt_state = AttemptState.FAILED
            attempt_update = {
                "attempt_state": next_attempt_state,
                "end_timestamp": ended_at,
                "failure_class": str(failure_class or "review_run_failed")[:200],
            }
        else:
            next_run_state = RunState.COMPLETED
            next_attempt_state = AttemptState.COMPLETED
            attempt_update = {
                "attempt_state": next_attempt_state,
                "end_timestamp": ended_at,
            }
        validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=next_attempt_state)
        attempt = await self.execution_repository.save_attempt_record(record=attempt.model_copy(update=attempt_update))
        validate_run_state_transition(current_state=run.lifecycle_state, next_state=next_run_state)
        closeout_ref = self.closeout_ref_for(run_id=run_id, failed=failed, failure_class=failure_class)
        step = await self.execution_repository.save_step_record(
            record=StepRecord(
                step_id=self.closeout_step_id_for(run_id=run_id),
                attempt_id=attempt.attempt_id,
                step_kind="review_run_closeout",
                input_ref=self.start_step_id_for(run_id=run_id),
                output_ref=closeout_ref,
                capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                resources_touched=[],
                observed_result_classification="review_run_failed" if failed else "review_run_completed",
                receipt_refs=[closeout_ref],
                closure_classification="step_completed",
            )
        )
        await self._ensure_effect(
            run=run,
            attempt=attempt,
            step=step,
            stage="closeout",
        )
        truth = await self.publication.publish_final_truth(
            final_truth_record_id=self.final_truth_id_for(run_id=run_id),
            run_id=run_id,
            result_class=ResultClass.FAILED if failed else ResultClass.SUCCESS,
            completion_classification=(
                CompletionClassification.UNSATISFIED if failed else CompletionClassification.SATISFIED
            ),
            evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
            residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
            degradation_classification=DegradationClassification.NONE,
            closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
            authority_sources=[AuthoritySourceClass.RECEIPT_EVIDENCE],
            authoritative_result_ref=closeout_ref,
        )
        run = await self.execution_repository.save_run_record(
            record=run.model_copy(
                update={
                    "lifecycle_state": next_run_state,
                    "final_truth_record_id": truth.final_truth_record_id,
                }
            )
        )
        return run, attempt

    @staticmethod
    def attempt_id_for(*, run_id: str) -> str:
        return f"{run_id}:attempt:0001"

    @staticmethod
    def start_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:start"

    @staticmethod
    def closeout_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:closeout"

    @staticmethod
    def admission_ref_for(*, snapshot: ReviewSnapshot) -> str:
        return f"review-run-snapshot:{snapshot.snapshot_digest}"

    @staticmethod
    def closeout_ref_for(*, run_id: str, failed: bool, failure_class: str) -> str:
        suffix = str(failure_class or "failed").strip() if failed else "completed"
        return f"{run_id}:closeout:{suffix}"

    @staticmethod
    def checkpoint_id_for(*, attempt_id: str) -> str:
        return f"review-run-checkpoint:{attempt_id}"

    @staticmethod
    def checkpoint_acceptance_id_for(*, attempt_id: str) -> str:
        return f"review-run-checkpoint-acceptance:{attempt_id}"

    @staticmethod
    def effect_id_for(*, run_id: str, stage: str) -> str:
        return f"review-run-effect:{run_id}:{stage}"

    @staticmethod
    def final_truth_id_for(*, run_id: str) -> str:
        return f"{run_id}:final_truth"

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
        return f"review-run-checkpoint-integrity:sha256:{hashlib.sha256(raw).hexdigest()}"

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise ReviewRunControlPlaneError(f"review run control-plane run missing: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str | None) -> AttemptRecord:
        normalized_attempt_id = str(attempt_id or "").strip()
        if not normalized_attempt_id:
            raise ReviewRunControlPlaneError("review run control-plane run is missing current_attempt_id")
        attempt = await self.execution_repository.get_attempt_record(attempt_id=normalized_attempt_id)
        if attempt is None:
            raise ReviewRunControlPlaneError(f"review run control-plane attempt missing: {normalized_attempt_id}")
        return attempt

    @staticmethod
    def _resources_touched(*, snapshot: ReviewSnapshot) -> list[str]:
        repo_id = str(snapshot.repo.get("repo_id") or "").strip()
        if repo_id:
            return [f"review-repo:{repo_id}", f"review-source:{snapshot.source}"]
        return [f"review-source:{snapshot.source}"]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

    async def _ensure_effect(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        step: StepRecord,
        stage: str,
    ):
        effect_id = self.effect_id_for(run_id=run.run_id, stage=stage)
        existing = await self.publication.repository.list_effect_journal_entries(run_id=run.run_id)
        for entry in existing:
            if entry.effect_id == effect_id:
                return entry
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=f"review-run-journal:{run.run_id}:{stage}",
            effect_id=effect_id,
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=run.admission_decision_receipt_ref,
            publication_timestamp=self._utc_now(),
            intended_target_ref=f"review-run:{run.run_id}:lifecycle",
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or run.admission_decision_receipt_ref,
        )


def build_review_run_control_plane_service(
    db_path: str | Path | None = None,
) -> ReviewRunControlPlaneService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return ReviewRunControlPlaneService(
        execution_repository=AsyncControlPlaneExecutionRepository(resolved_db_path),
        publication=publication,
    )


__all__ = [
    "ReviewRunControlPlaneError",
    "ReviewRunControlPlaneService",
    "build_review_run_control_plane_service",
]
