"""Layer: integration. Scheduler publication consumes the pipeline's supplied clock."""
import pytest

from orket.application.services.orchestrator_issue_control_plane_support import (
    child_workload_run_id_for_issue_creation,
    lease_id_for_run,
    scheduler_run_id_for_transition,
)
from orket.application.services.orchestrator_scheduler_control_plane_service import (
    OrchestratorSchedulerControlPlaneService,
)
from orket.core.domain.control_plane_leases import ControlPlaneLeaseError
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("kind", ["transition", "child"])
@pytest.mark.parametrize("fail_promotion", [False, True])
async def test_pipeline_scheduler_publications_use_supplied_clock(
    test_root, workspace, db_path, kind, fail_promotion, monkeypatch,
):
    clock = ProtocolLedgerClock()
    clock.current = clock.current.replace(year=2041)
    async with ExecutionPipeline.open(workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock) as pipeline:
        try:
            scheduler = pipeline.orchestrator.scheduler_control_plane
            before = clock.utc_now_iso()
            if fail_promotion:
                async def reject_promotion(**kwargs):
                    raise RuntimeError("controlled promotion failure")
                monkeypatch.setattr(scheduler.publication, "promote_reservation_to_lease", reject_promotion)
            if kind == "transition":
                run_id = scheduler_run_id_for_transition(
                    session_id="scheduler-clock", issue_id="ISSUE-CLOCK", current_status="ready",
                    target_status="blocked", reason="dependency_blocked")
                operation = scheduler.publish_scheduler_transition(
                    session_id="scheduler-clock", issue_id="ISSUE-CLOCK", current_status="ready",
                    target_status="blocked", reason="dependency_blocked", assignee="coder")
            else:
                run_id = child_workload_run_id_for_issue_creation(
                    session_id="scheduler-clock", child_issue_id="CHILD-CLOCK", relationship_class="follow_up",
                    metadata={"active_build": "build-clock", "seat_name": "coder", "trigger_issue_ids": ["ISSUE-CLOCK"]})
                operation = scheduler.publish_child_issue_creation(
                    session_id="scheduler-clock", issue_id="CHILD-CLOCK", active_build="build-clock",
                    seat_name="coder", relationship_class="follow_up", trigger_issue_ids=["ISSUE-CLOCK"])
            if fail_promotion:
                with pytest.raises(RuntimeError, match="controlled promotion failure"):
                    await operation
            else:
                assert await operation == run_id
            run = await scheduler.execution_repository.get_run_record(run_id=run_id)
            lease = await scheduler.publication.repository.get_latest_lease_record(lease_id=lease_id_for_run(run_id=run_id))
            assert run is not None and lease is not None
            assert before < run.creation_timestamp == lease.granted_timestamp < lease.publication_timestamp < clock.utc_now_iso()
            assert lease.status.value == "lease_released"
        finally:
            await pipeline.close()


async def test_scheduler_rejects_retained_reversed_clock_without_fabricating_release(test_root, workspace, db_path):
    async with ExecutionPipeline.open(workspace=workspace, config_root=test_root, db_path=db_path) as pipeline:
        supplied = iter(["2026-09-18T02:53:30.537287+00:00", "2026-09-18T02:53:21.228116+00:00"])
        try:
            owner = pipeline.orchestrator.scheduler_control_plane
            scheduler = OrchestratorSchedulerControlPlaneService(
                execution_repository=owner.execution_repository, publication=owner.publication, now_utc=supplied.__next__)
            with pytest.raises(ControlPlaneLeaseError, match="timestamps must increase monotonically"):
                await scheduler.publish_scheduler_transition(
                    session_id="scheduler-reversal", issue_id="ISSUE-CLOCK", current_status="code_review",
                    target_status="ready", reason="runtime_guard_retry_scheduled", assignee="coder")
            run_id = scheduler_run_id_for_transition(
                session_id="scheduler-reversal", issue_id="ISSUE-CLOCK", current_status="code_review",
                target_status="ready", reason="runtime_guard_retry_scheduled")
            lease = await scheduler.publication.repository.get_latest_lease_record(
                lease_id=lease_id_for_run(run_id=run_id))
            assert lease is not None and lease.status.value == "lease_active"
            assert lease.publication_timestamp == "2026-09-18T02:53:30.537287+00:00"
            # This proves rejection and no invented release, not atomic scheduler closeout.
        finally:
            await pipeline.close()
