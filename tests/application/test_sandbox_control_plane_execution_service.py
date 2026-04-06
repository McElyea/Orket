# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_workload_catalog import (
    sandbox_runtime_workload_for_tech_stack,
)
from orket.application.services.sandbox_control_plane_execution_service import (
    SandboxControlPlaneExecutionError,
    SandboxControlPlaneExecutionService,
)
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.contracts import AttemptRecord, CheckpointRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository, ControlPlaneRecordRepository
from orket.core.domain import (
    AttemptState,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    FailurePlane,
    RecoveryActionClass,
    ResourceFailureClass,
    RunState,
)
from orket.core.domain.sandbox_lifecycle import TerminalReason
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository

pytestmark = pytest.mark.unit


class InMemoryControlPlaneExecutionRepository(ControlPlaneExecutionRepository):
    def __init__(self) -> None:
        self.run_by_id: dict[str, RunRecord] = {}
        self.attempt_by_id: dict[str, AttemptRecord] = {}
        self.step_by_id: dict[str, StepRecord] = {}

    async def save_run_record(self, *, record: RunRecord) -> RunRecord:
        self.run_by_id[record.run_id] = record
        return record

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        return self.run_by_id.get(run_id)

    async def save_attempt_record(self, *, record: AttemptRecord) -> AttemptRecord:
        self.attempt_by_id[record.attempt_id] = record
        return record

    async def get_attempt_record(self, *, attempt_id: str) -> AttemptRecord | None:
        return self.attempt_by_id.get(attempt_id)

    async def list_attempt_records(self, *, run_id: str) -> list[AttemptRecord]:
        return sorted(
            [record for record in self.attempt_by_id.values() if record.run_id == run_id],
            key=lambda item: item.attempt_ordinal,
        )

    async def save_step_record(self, *, record: StepRecord) -> StepRecord:
        self.step_by_id[record.step_id] = record
        return record

    async def get_step_record(self, *, step_id: str) -> StepRecord | None:
        return self.step_by_id.get(step_id)

    async def list_step_records(self, *, attempt_id: str) -> list[StepRecord]:
        return sorted(
            [record for record in self.step_by_id.values() if record.attempt_id == attempt_id],
            key=lambda item: item.step_id,
        )


@pytest.mark.asyncio
async def test_execution_service_initializes_and_rolls_new_attempt_after_reacquire() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=publication_repo),
    )

    run, attempt = await service.initialize_execution(
        sandbox_id="sb-1",
        run_id="run-1",
        workload=sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres"),
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-24T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-1",
        policy=SandboxLifecyclePolicy(),
    )
    policy_snapshot = await publication_repo.get_resolved_policy_snapshot(snapshot_id=run.policy_snapshot_id)
    configuration_snapshot = await publication_repo.get_resolved_configuration_snapshot(
        snapshot_id=run.configuration_snapshot_id
    )

    waiting_run, waiting_attempt = await service.mark_waiting_on_resource(
        run_id="run-1",
        observed_at="2026-03-24T00:05:00+00:00",
    )
    checkpoint = await service.publication.publish_checkpoint(
        checkpoint=CheckpointRecord(
            checkpoint_id="sandbox-checkpoint:sb-1:lease_epoch:00000001",
            parent_ref=waiting_attempt.attempt_id,
            creation_timestamp="2026-03-24T00:05:00+00:00",
            state_snapshot_ref="sandbox-lifecycle-snapshot:sb-1:00000004",
            resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
            invalidation_conditions=["policy_digest_mismatch"],
            dependent_resource_ids=["sandbox-scope:sb-1"],
            dependent_effect_refs=[],
            policy_digest=waiting_run.policy_digest,
            integrity_verification_ref="sha256:snapshot",
        )
    )
    acceptance = await service.publication.accept_checkpoint(
        acceptance_id="sandbox-checkpoint-acceptance:sb-1:lease_epoch:00000001",
        checkpoint=checkpoint,
        supervisor_authority_ref="sandbox-reconciliation:run-1:00000004",
        decision_timestamp="2026-03-24T00:05:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.FULL,
        integrity_verification_ref="sha256:snapshot",
    )
    resumed_run, resumed_attempt, decision = await service.start_new_attempt_after_reacquire(
        sandbox_id="sb-1",
        run_id="run-1",
        lease_epoch=2,
        observed_at="2026-03-24T00:06:00+00:00",
        policy_version="docker_sandbox_lifecycle.v1",
        rationale_ref="sandbox-reconciliation:run-1:00000004",
    )

    assert run.lifecycle_state is RunState.EXECUTING
    assert run.workload_id == "sandbox-workload:fastapi-react-postgres"
    assert run.workload_version == "docker_sandbox_runtime.v1"
    assert attempt.attempt_state is AttemptState.EXECUTING
    assert policy_snapshot is not None
    assert configuration_snapshot is not None
    assert policy_snapshot.snapshot_digest == run.policy_digest
    assert configuration_snapshot.snapshot_digest == run.configuration_digest
    assert waiting_run.lifecycle_state is RunState.WAITING_ON_RESOURCE
    assert waiting_attempt.attempt_state is AttemptState.INTERRUPTED
    assert waiting_attempt.failure_plane is FailurePlane.RESOURCE
    assert waiting_attempt.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE
    assert resumed_run.lifecycle_state is RunState.EXECUTING
    assert resumed_run.current_attempt_id == resumed_attempt.attempt_id
    assert resumed_attempt.attempt_state is AttemptState.EXECUTING
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.RESUME_FROM_CHECKPOINT
    assert decision.failure_plane is FailurePlane.RESOURCE
    assert decision.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE
    assert decision.new_attempt_id == resumed_attempt.attempt_id
    assert decision.target_checkpoint_id == checkpoint.checkpoint_id
    assert decision.required_precondition_refs == [checkpoint.checkpoint_id, acceptance.acceptance_id]
    interrupted_attempt = await execution_repo.get_attempt_record(attempt_id=waiting_attempt.attempt_id)
    assert interrupted_attempt is not None
    assert interrupted_attempt.recovery_decision_id == decision.decision_id


@pytest.mark.asyncio
async def test_execution_service_finalizes_terminal_run_and_attempt() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=publication_repo),
    )

    await service.initialize_execution(
        sandbox_id="sb-2",
        run_id="run-2",
        workload=sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres"),
        compose_project="orket-sandbox-sb-2",
        workspace_path="workspace/sb-2",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-24T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-2",
        policy=SandboxLifecyclePolicy(),
    )

    run, attempt, decision = await service.finalize_terminal_execution(
        run_id="run-2",
        observed_at="2026-03-24T00:03:00+00:00",
        terminal_reason=TerminalReason.LOST_RUNTIME,
        policy_version="docker_sandbox_lifecycle.v1",
        final_truth_record_id="truth-2",
        rationale_ref="sandbox-reconciliation:run-2:00000004",
        recovery_rationale_ref="sandbox-reconciliation:run-2:00000004",
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id == "truth-2"
    assert attempt is not None
    assert attempt.attempt_state is AttemptState.INTERRUPTED
    assert attempt.failure_plane is FailurePlane.RESOURCE
    assert attempt.failure_classification is ResourceFailureClass.RESOURCE_STATE_UNCERTAIN
    assert attempt.recovery_decision_id is not None
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_plane is FailurePlane.RESOURCE
    assert decision.failure_classification is ResourceFailureClass.RESOURCE_STATE_UNCERTAIN


@pytest.mark.asyncio
async def test_execution_service_finalizes_hard_max_age_with_resource_failure_taxonomy() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=publication_repo),
    )

    await service.initialize_execution(
        sandbox_id="sb-3",
        run_id="run-3",
        workload=sandbox_runtime_workload_for_tech_stack("fastapi-react-postgres"),
        compose_project="orket-sandbox-sb-3",
        workspace_path="workspace/sb-3",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-24T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-3",
        policy=SandboxLifecyclePolicy(),
    )

    run, attempt, decision = await service.finalize_terminal_execution(
        run_id="run-3",
        observed_at="2026-03-24T00:09:00+00:00",
        terminal_reason=TerminalReason.HARD_MAX_AGE,
        policy_version="docker_sandbox_lifecycle.v1",
        final_truth_record_id="truth-3",
        rationale_ref="sandbox-reconciliation:run-3:00000009",
    )

    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert run.final_truth_record_id == "truth-3"
    assert attempt is not None
    assert attempt.attempt_state is AttemptState.FAILED
    assert attempt.failure_plane is FailurePlane.RESOURCE
    assert attempt.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.failure_plane is FailurePlane.RESOURCE
    assert decision.failure_classification is ResourceFailureClass.RESOURCE_UNAVAILABLE


@pytest.mark.asyncio
async def test_execution_service_fails_closed_on_mismatched_sandbox_workload_authority() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=ControlPlanePublicationService(repository=publication_repo),
    )

    with pytest.raises(SandboxControlPlaneExecutionError, match="sandbox workload authority mismatch"):
        await service.initialize_execution(
            sandbox_id="sb-mismatch",
            run_id="run-mismatch",
            workload=sandbox_runtime_workload_for_tech_stack("fastapi-vue-mongo"),
            compose_project="orket-sandbox-sb-mismatch",
            workspace_path="workspace/sb-mismatch",
            configuration_payload={"tech_stack": "fastapi-react-postgres"},
            creation_timestamp="2026-03-24T00:00:00+00:00",
            admission_decision_receipt_ref="sandbox-reservation:sb-mismatch",
            policy=SandboxLifecyclePolicy(),
        )
