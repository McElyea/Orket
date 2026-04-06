# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_target_resource_refs import (
    resource_id_for_supported_run,
)
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.core.contracts.control_plane_models import RunRecord
from orket.core.domain import (
    CleanupAuthorityClass,
    OperatorInputClass,
    OrphanClassification,
    OwnershipClass,
    RunState,
)
from orket.orchestration.approval_control_plane_read_model import target_resource_summary
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository
from tests.application.test_sandbox_control_plane_execution_service import InMemoryControlPlaneExecutionRepository

pytestmark = pytest.mark.unit


def _run_record(*, run_id: str, namespace_scope: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        workload_id="test-workload",
        workload_version="v1",
        policy_snapshot_id=f"policy:{run_id}",
        policy_digest="sha256:policy",
        configuration_snapshot_id=f"config:{run_id}",
        configuration_digest="sha256:config",
        creation_timestamp="2026-03-27T12:00:00+00:00",
        admission_decision_receipt_ref=f"receipt:{run_id}",
        namespace_scope=namespace_scope,
        lifecycle_state=RunState.EXECUTING,
        current_attempt_id=f"{run_id}:attempt:0001",
    )


def test_resource_id_for_supported_run_maps_orchestrator_issue_and_namespace_runs() -> None:
    issue_dispatch_run = _run_record(
        run_id="orchestrator-issue-run:sess-issue:ISS-42:developer:0003",
        namespace_scope="issue:ISS-42",
    )
    scheduler_run = _run_record(
        run_id="orchestrator-issue-scheduler-run:sess-issue:ISS-42:blocked:abc123def4567890",
        namespace_scope="issue:ISS-42",
    )
    child_workload_run = _run_record(
        run_id="orchestrator-child-workload-run:sess-issue:ISS-42:child_workload:abc123def4567890",
        namespace_scope="issue:ISS-42",
    )

    assert resource_id_for_supported_run(run=issue_dispatch_run) == "issue-dispatch-slot:sess-issue:ISS-42"
    assert resource_id_for_supported_run(run=scheduler_run) == "namespace:issue:ISS-42"
    assert resource_id_for_supported_run(run=child_workload_run) == "namespace:issue:ISS-42"


@pytest.mark.asyncio
async def test_target_resource_summary_projects_orchestrator_issue_dispatch_resource() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    execution_repository = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=repository)
    run = _run_record(
        run_id="orchestrator-issue-run:sess-issue:ISS-42:developer:0003",
        namespace_scope="issue:ISS-42",
    )
    await execution_repository.save_run_record(record=run)
    await publication.publish_resource(
        resource_id="issue-dispatch-slot:sess-issue:ISS-42",
        resource_kind="issue_dispatch_slot",
        namespace_scope="issue:ISS-42",
        ownership_class=OwnershipClass.RUN_OWNED,
        current_observed_state="lease_status:lease_active;namespace:issue:ISS-42",
        last_observed_timestamp="2026-03-27T12:00:05+00:00",
        cleanup_authority_class=CleanupAuthorityClass.RUNTIME_CLEANUP_ALLOWED,
        provenance_ref="orchestrator-issue-lease:orchestrator-issue-run:sess-issue:ISS-42:developer:0003",
        reconciliation_status="governed_execution_authority",
        orphan_classification=OrphanClassification.NOT_ORPHANED,
    )

    summary = await target_resource_summary(
        repository=repository,
        execution_repository=execution_repository,
        run_id=run.run_id,
    )

    assert summary is not None
    assert summary["resource_id"] == "issue-dispatch-slot:sess-issue:ISS-42"
    assert summary["resource_kind"] == "issue_dispatch_slot"
    assert summary["namespace_scope"] == "issue:ISS-42"


@pytest.mark.asyncio
async def test_tool_approval_operator_action_includes_orchestrator_issue_dispatch_resource_ref() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    execution_repository = InMemoryControlPlaneExecutionRepository()
    publication = ControlPlanePublicationService(repository=repository)
    service = ToolApprovalControlPlaneOperatorService(
        publication=publication,
        execution_repository=execution_repository,
    )
    run_id = "orchestrator-issue-run:sess-issue:ISS-42:developer:0003"
    await execution_repository.save_run_record(
        record=_run_record(
            run_id=run_id,
            namespace_scope="issue:ISS-42",
        )
    )

    await service.publish_resolution_operator_action(
        actor_ref="api_key_fingerprint:sha256:test",
        previous_approval={
            "approval_id": "apr-issue-42",
            "status": "PENDING",
        },
        resolved_approval={
            "approval_id": "apr-issue-42",
            "session_id": "sess-issue",
            "issue_id": "ISS-42",
            "gate_mode": "approval_required",
            "request_type": "tool_approval",
            "reason": "approval_required_tool:write_file",
            "payload": {
                "control_plane_target_ref": run_id,
            },
            "status": "APPROVED",
            "resolution": {
                "decision": "approve",
            },
            "updated_at": "2026-03-27T12:00:10+00:00",
        },
    )

    approval_actions = await repository.list_operator_actions(target_ref="approval-request:apr-issue-42")
    run_actions = await repository.list_operator_actions(target_ref=run_id)

    assert len(approval_actions) == 1
    assert len(run_actions) == 1
    assert approval_actions[0].input_class is OperatorInputClass.RISK_ACCEPTANCE
    assert run_actions[0].input_class is OperatorInputClass.RISK_ACCEPTANCE
    assert approval_actions[0].affected_resource_refs == [
        "session:sess-issue",
        "issue:ISS-42",
        "issue-dispatch-slot:sess-issue:ISS-42",
    ]
    assert run_actions[0].affected_resource_refs == [
        "session:sess-issue",
        "issue:ISS-42",
        "issue-dispatch-slot:sess-issue:ISS-42",
        run_id,
    ]
