# Layer: unit

from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.application.services.control_plane_workload_catalog import ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.orchestrator_issue_control_plane_support import lease_id_for_run
from orket.application.services.orchestrator_scheduler_control_plane_mutation import (
    activate_namespace_authority,
    close_namespace_mutation,
    create_namespace_execution,
)
from orket.core.contracts import AttemptRecord, RunRecord
from orket.core.domain import (
    AttemptState,
    ClosureBasisClassification,
    CompletionClassification,
    ControlPlaneLifecycleError,
    LeaseStatus,
    ReservationStatus,
    ResultClass,
    RunState,
)
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_close_namespace_mutation_uses_current_lifecycle_state_guards() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    run = await execution_repo.save_run_record(
        record=RunRecord(
            run_id="scheduler-run-guard-1",
            workload_id=ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_id,
            workload_version=ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_version,
            policy_snapshot_id="scheduler-policy-guard-1",
            policy_digest="sha256:scheduler-policy-guard-1",
            configuration_snapshot_id="scheduler-config-guard-1",
            configuration_digest="sha256:scheduler-config-guard-1",
            creation_timestamp="2026-03-25T19:00:00+00:00",
            admission_decision_receipt_ref="scheduler-admission-guard-1",
            namespace_scope="issue:ISSUE-1",
            lifecycle_state=RunState.ADMITTED,
            current_attempt_id="scheduler-attempt-guard-1",
        )
    )
    attempt = await execution_repo.save_attempt_record(
        record=AttemptRecord(
            attempt_id="scheduler-attempt-guard-1",
            run_id=run.run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.CREATED,
            starting_state_snapshot_ref="scheduler-admission-guard-1",
            start_timestamp="2026-03-25T19:00:00+00:00",
        )
    )

    with pytest.raises(ControlPlaneLifecycleError, match="Illegal control-plane"):
        await close_namespace_mutation(
            execution_repository=execution_repo,
            publication=publication,
            run=run,
            attempt=attempt,
            lease=SimpleNamespace(
                lease_id="scheduler-lease-guard-1",
                resource_id="namespace:issue:ISSUE-1",
                holder_ref="orchestrator:scheduler",
                lease_epoch=1,
                cleanup_eligibility_rule="release_on_closeout",
                source_reservation_id="scheduler-reservation-guard-1",
            ),
            workload=ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
            step_kind="scheduler_guard_test",
            output_ref="scheduler-guard-output-ref",
            result_class=ResultClass.SUCCESS,
            completion_classification=CompletionClassification.SATISFIED,
            closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
            ended_at="2026-03-25T19:00:05+00:00",
        )


@pytest.mark.asyncio
async def test_activate_namespace_authority_fail_closes_reservation_and_lease_on_promotion_failure() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    record_repo = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=record_repo)
    run, attempt = await create_namespace_execution(
        execution_repository=execution_repo,
        publication=publication,
        run_id="scheduler-run-guard-2",
        workload=ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
        issue_id="ISSUE-2",
        admission_ref="scheduler-admission-guard-2",
        policy_payload={"reason": "dependency_blocked"},
        config_payload={"issue_id": "ISSUE-2"},
        created_at="2026-03-25T19:10:00+00:00",
    )

    async def _raise_promote_failure(**_kwargs) -> None:
        raise RuntimeError("promote failed")

    publication.promote_reservation_to_lease = _raise_promote_failure  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="promote failed"):
        await activate_namespace_authority(
            execution_repository=execution_repo,
            publication=publication,
            promotion_rule="promote_on_scheduler_mutation_start",
            cleanup_rule="release_on_scheduler_mutation_closeout",
            run=run,
            attempt=attempt,
            workload=ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD,
            holder_ref="orchestrator:scheduler:issue:ISSUE-2",
            issue_id="ISSUE-2",
            step_kind="issue_status_transition",
            created_at="2026-03-25T19:10:00+00:00",
        )

    reservation = await record_repo.get_latest_reservation_record(
        reservation_id=(
            f"{ORCHESTRATOR_SCHEDULER_TRANSITION_WORKLOAD.workload_id}-reservation:scheduler-run-guard-2"
        )
    )
    lease = await record_repo.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run.run_id))
    resource_history = await record_repo.list_resource_records(resource_id="namespace:issue:ISSUE-2")
    updated_run = await execution_repo.get_run_record(run_id=run.run_id)

    assert updated_run is not None
    assert updated_run.lifecycle_state is RunState.ADMITTED
    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert [record.current_observed_state.split(";")[0] for record in resource_history] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]
