# Layer: integration

from __future__ import annotations

from pathlib import Path

import aiofiles
import pytest

from orket.adapters.storage.command_runner import CommandResult
from orket.core.domain import AttemptState, ClosureBasisClassification, LeaseStatus, ReservationStatus, ResultClass, RunState
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator


class FakeLifecycleRunner:
    def __init__(
        self,
        *,
        compose_project: str,
        sandbox_id: str,
        run_id: str,
        down_returncode: int = 0,
        container_state: str = "running",
        list_returncode: int = 0,
    ):
        self.compose_project = compose_project
        self.sandbox_id = sandbox_id
        self.run_id = run_id
        self.down_returncode = down_returncode
        self.container_state = container_state
        self.list_returncode = list_returncode
        self.resources_present = True
        self.async_calls: list[tuple[str, ...]] = []

    async def run_async(self, *cmd: str) -> CommandResult:
        self.async_calls.append(cmd)
        if cmd[:2] == ("docker-compose", "-f") and "up" in cmd:
            return CommandResult(returncode=0, stdout="", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "down" in cmd:
            self.resources_present = False
            return CommandResult(returncode=self.down_returncode, stdout="", stderr="compose-down-warning")
        if cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "-q" in cmd:
            return CommandResult(returncode=0, stdout="cid-1\n", stderr="")
        if cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "--format" in cmd:
            return CommandResult(
                returncode=0,
                stdout='{"Service":"api","State":"running","Name":"%s-api-1"}\n' % self.compose_project,
                stderr="",
            )
        if cmd[:2] == ("docker", "inspect"):
            return CommandResult(returncode=0, stdout=self._inspect_payload(), stderr="")
        if cmd[:3] == ("docker", "ps", "-a"):
            return CommandResult(
                returncode=self.list_returncode,
                stdout=self._container_rows() if self.list_returncode == 0 else "",
                stderr="" if self.list_returncode == 0 else "docker ps unavailable",
            )
        if cmd[:3] == ("docker", "network", "ls"):
            return CommandResult(
                returncode=self.list_returncode,
                stdout=self._network_rows() if self.list_returncode == 0 else "",
                stderr="" if self.list_returncode == 0 else "docker network ls unavailable",
            )
        if cmd[:3] == ("docker", "volume", "ls"):
            return CommandResult(
                returncode=self.list_returncode,
                stdout=self._volume_rows() if self.list_returncode == 0 else "",
                stderr="" if self.list_returncode == 0 else "docker volume ls unavailable",
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    def run_sync(self, *cmd: str, timeout=None) -> CommandResult:
        return CommandResult(returncode=0, stdout="logs", stderr="")

    def _container_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Names":"%s-api-1","State":"%s","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s,com.docker.compose.service=api"}\n'
            % (self.compose_project, self.container_state, self.sandbox_id, self.run_id)
        )

    def _network_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_default","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _volume_rows(self) -> str:
        if not self.resources_present:
            return ""
        return (
            '{"Name":"%s_db-data","Labels":"orket.managed=true,orket.sandbox_id=%s,orket.run_id=%s"}\n'
            % (self.compose_project, self.sandbox_id, self.run_id)
        )

    def _inspect_payload(self) -> str:
        health = ""
        if self.container_state == "running":
            health = ',"Health":{"Status":"healthy"}'
        return (
            '[{"Name":"/%s-api-1","RestartCount":0,"Config":{"Labels":{"com.docker.compose.service":"api"}},"State":{"Status":"%s"%s}}]'
            % (self.compose_project, self.container_state, health)
        )


def _orchestrator(tmp_path: Path, runner: FakeLifecycleRunner) -> SandboxOrchestrator:
    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        command_runner=runner,
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    return orchestrator


@pytest.mark.asyncio
async def test_create_sandbox_persists_active_lifecycle_and_operator_view(tmp_path) -> None:
    sandbox_id = "sandbox-rock-1"
    compose_project = "orket-sandbox-rock-1"
    runner = FakeLifecycleRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="rock-1")
    orchestrator = _orchestrator(tmp_path, runner)

    sandbox = await orchestrator.create_sandbox(
        rock_id="rock-1",
        project_name="Integration Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
    reservation = await orchestrator.control_plane_repository.get_latest_reservation_record(
        reservation_id=f"sandbox-reservation:{sandbox_id}"
    )
    reservation_history = await orchestrator.control_plane_repository.list_reservation_records(
        reservation_id=f"sandbox-reservation:{sandbox_id}"
    )
    run = await orchestrator.control_plane_execution_repository.get_run_record(run_id="rock-1")
    attempts = await orchestrator.control_plane_execution_repository.list_attempt_records(run_id="rock-1")
    journal_entries = await orchestrator.control_plane_repository.list_effect_journal_entries(run_id="rock-1")
    lease = await orchestrator.control_plane_repository.get_latest_lease_record(
        lease_id=f"sandbox-lease:{sandbox_id}"
    )
    views = await orchestrator.list_sandboxes()
    workspace_token = str(tmp_path).replace("\\", "/").strip("/")

    assert sandbox.status.value == "running"
    assert record is not None
    assert record.state.value == "active"
    assert record.managed_resource_inventory.containers == [f"{compose_project}-api-1"]
    assert record.managed_resource_inventory.networks == [f"{compose_project}_default"]
    assert record.managed_resource_inventory.managed_volumes == [f"{compose_project}_db-data"]
    assert reservation is not None
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert [item.status for item in reservation_history] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert run is not None
    assert run.lifecycle_state is RunState.EXECUTING
    assert run.current_attempt_id == f"sandbox-attempt:{sandbox_id}:00000001"
    assert len(attempts) == 1
    assert attempts[0].attempt_state is AttemptState.EXECUTING
    assert [entry.effect_id for entry in journal_entries] == [
        f"sandbox-effect:{sandbox_id}:deploy:lease_epoch:00000001"
    ]
    assert journal_entries[0].attempt_id == attempts[0].attempt_id
    assert lease is not None
    assert lease.status is LeaseStatus.ACTIVE
    assert lease.lease_epoch == 1
    assert lease.source_reservation_id == reservation.reservation_id
    assert views[0]["sandbox_id"] == sandbox_id
    assert views[0]["compose_project"] == compose_project
    assert views[0]["state"] == "active"
    assert views[0]["requires_reconciliation"] is False
    assert views[0]["control_plane_run_state"] == "executing"
    assert views[0]["control_plane_current_attempt_id"] == f"sandbox-attempt:{sandbox_id}:00000001"
    assert views[0]["control_plane_current_attempt_state"] == "attempt_executing"
    assert views[0]["control_plane_recovery_decision_id"] is None
    assert views[0]["control_plane_checkpoint_id"] is None
    assert views[0]["control_plane_checkpoint_resumability_class"] is None
    assert views[0]["control_plane_checkpoint_acceptance_outcome"] is None
    assert views[0]["control_plane_reconciliation_id"] is None
    assert views[0]["control_plane_divergence_class"] is None
    assert views[0]["control_plane_safe_continuation_class"] is None
    assert views[0]["control_plane_reservation_status"] == "reservation_promoted_to_lease"
    assert views[0]["control_plane_lease_status"] == "lease_active"
    assert views[0]["final_truth_record_id"] is None
    assert views[0]["control_plane_final_result_class"] is None
    assert views[0]["control_plane_final_closure_basis"] is None
    assert views[0]["control_plane_final_terminality_basis"] is None
    assert views[0]["control_plane_final_evidence_sufficiency_class"] is None
    assert views[0]["control_plane_final_residual_uncertainty_class"] is None
    assert views[0]["control_plane_final_degradation_class"] is None
    assert views[0]["control_plane_final_authoritative_result_ref"] is None
    assert views[0]["control_plane_final_authority_sources"] == []
    assert views[0]["effect_journal_entry_count"] == 1
    assert views[0]["latest_effect_journal_entry_id"] == (
        f"sandbox-journal:{sandbox_id}:deploy:lease_epoch:00000001"
    )
    assert views[0]["latest_effect_id"] == f"sandbox-effect:{sandbox_id}:deploy:lease_epoch:00000001"
    assert views[0]["latest_effect_intended_target_ref"] == f"sandbox-runtime:{compose_project}"
    assert views[0]["latest_effect_observed_result_ref"] is not None
    assert views[0]["latest_effect_observed_result_ref"].startswith(
        f"sandbox-deploy-observation:{sandbox_id}:"
    )
    assert views[0]["latest_effect_observed_result_ref"].endswith(f":{workspace_token}")
    assert views[0]["latest_effect_authorization_basis_ref"] == reservation.reservation_id
    assert views[0]["latest_effect_integrity_verification_ref"] is not None
    assert views[0]["latest_effect_integrity_verification_ref"].startswith(
        f"sandbox-health-verification:{sandbox_id}:"
    )
    assert views[0]["latest_effect_uncertainty_classification"] == "no_residual_uncertainty"
    assert views[0]["operator_action_count"] == 0
    assert views[0]["latest_operator_action"] is None


@pytest.mark.asyncio
async def test_delete_sandbox_marks_cleaned_after_live_absence_even_if_down_warns(tmp_path) -> None:
    sandbox_id = "sandbox-rock-2"
    compose_project = "orket-sandbox-rock-2"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-2",
        down_returncode=1,
    )
    orchestrator = _orchestrator(tmp_path, runner)
    orchestrator.lifecycle_service.terminal_evidence = SandboxTerminalEvidenceService(
        evidence_root=tmp_path / "terminal_evidence"
    )

    await orchestrator.create_sandbox(
        rock_id="rock-2",
        project_name="Cleanup Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    await orchestrator.delete_sandbox(sandbox_id, operator_actor_ref="operator:test")

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
    lease = await orchestrator.control_plane_repository.get_latest_lease_record(
        lease_id=f"sandbox-lease:{sandbox_id}"
    )
    final_truth = await orchestrator.control_plane_repository.get_final_truth(run_id="rock-2")
    operator_actions = await orchestrator.control_plane_repository.list_operator_actions(target_ref="rock-2")
    journal_entries = await orchestrator.control_plane_repository.list_effect_journal_entries(run_id="rock-2")
    events = await orchestrator.lifecycle_service.repository.list_events(sandbox_id)
    views = await orchestrator.list_sandboxes()
    workspace_token = str(tmp_path).replace("\\", "/").strip("/")

    assert record is not None
    assert record.state.value == "cleaned"
    assert record.cleanup_state.value == "completed"
    assert record.cleanup_attempts == 1
    assert record.required_evidence_ref is not None
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    async with aiofiles.open(record.required_evidence_ref, "r", encoding="utf-8") as handle:
        evidence = await handle.read()
    assert "sandbox_cancellation_receipt" in evidence
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.CANCELLED_BY_AUTHORITY
    assert len(operator_actions) == 1
    assert operator_actions[0].actor_ref == "operator:test"
    assert views[0]["control_plane_run_state"] == "cancelled"
    assert views[0]["control_plane_current_attempt_state"] == "attempt_abandoned"
    assert views[0]["control_plane_recovery_decision_id"] is None
    assert views[0]["control_plane_checkpoint_id"] is None
    assert views[0]["control_plane_checkpoint_resumability_class"] is None
    assert views[0]["control_plane_checkpoint_acceptance_outcome"] is None
    assert views[0]["control_plane_reconciliation_id"] is None
    assert views[0]["control_plane_divergence_class"] is None
    assert views[0]["control_plane_safe_continuation_class"] is None
    assert views[0]["control_plane_reservation_status"] == "reservation_promoted_to_lease"
    assert views[0]["control_plane_lease_status"] == "lease_released"
    assert views[0]["final_truth_record_id"] == final_truth.final_truth_record_id
    assert views[0]["control_plane_final_result_class"] == "blocked"
    assert views[0]["control_plane_final_closure_basis"] == "cancelled_by_authority"
    assert views[0]["control_plane_final_terminality_basis"] == "cancelled_terminal"
    assert views[0]["control_plane_final_evidence_sufficiency_class"] == "evidence_sufficient"
    assert views[0]["control_plane_final_residual_uncertainty_class"] == "no_residual_uncertainty"
    assert views[0]["control_plane_final_degradation_class"] == "no_degradation"
    assert views[0]["control_plane_final_authoritative_result_ref"] == record.required_evidence_ref
    assert views[0]["control_plane_final_authority_sources"] == ["receipt_evidence"]
    assert views[0]["effect_journal_entry_count"] == 2
    assert views[0]["latest_effect_journal_entry_id"] == (
        f"sandbox-journal:{sandbox_id}:cleanup:lease_epoch:00000001"
    )
    assert views[0]["latest_effect_id"] == f"sandbox-effect:{sandbox_id}:cleanup:lease_epoch:00000001"
    assert views[0]["latest_effect_intended_target_ref"] == f"sandbox-runtime:{compose_project}"
    assert views[0]["latest_effect_observed_result_ref"] is not None
    assert views[0]["latest_effect_observed_result_ref"].startswith(
        f"sandbox-cleanup-verification:{sandbox_id}:verified_complete:"
    )
    assert views[0]["latest_effect_observed_result_ref"].endswith(f":{workspace_token}")
    assert views[0]["latest_effect_authorization_basis_ref"] == (
        f"sandbox-cleanup-authority:{sandbox_id}:lease_epoch:00000001"
    )
    assert views[0]["latest_effect_integrity_verification_ref"] is not None
    assert views[0]["latest_effect_integrity_verification_ref"].startswith(
        f"sandbox-cleanup-verification:{sandbox_id}:"
    )
    assert views[0]["latest_effect_uncertainty_classification"] == "no_residual_uncertainty"
    assert views[0]["operator_action_count"] == 1
    assert views[0]["latest_operator_action"]["command_class"] == "cancel_run"
    assert views[0]["latest_operator_action"]["receipt_refs"] == operator_actions[0].receipt_refs
    assert [entry.effect_id for entry in journal_entries] == [
        f"sandbox-effect:{sandbox_id}:deploy:lease_epoch:00000001",
        f"sandbox-effect:{sandbox_id}:cleanup:lease_epoch:00000001",
    ]
    assert any(event.event_type == "sandbox.workflow_terminal_outcome" for event in events)


@pytest.mark.asyncio
async def test_delete_sandbox_retries_terminal_records_after_a_failed_cleanup_attempt(tmp_path) -> None:
    sandbox_id = "sandbox-rock-2b"
    compose_project = "orket-sandbox-rock-2b"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-2b",
        down_returncode=1,
    )
    orchestrator = _orchestrator(tmp_path, runner)

    sandbox = await orchestrator.create_sandbox(
        rock_id="rock-2b",
        project_name="Cleanup Retry Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
    assert record is not None
    await orchestrator.lifecycle_service.repository.save_record(
        record.model_copy(
            update={
                "state": SandboxState.TERMINAL,
                "cleanup_state": CleanupState.FAILED,
                "record_version": record.record_version + 1,
                "terminal_reason": TerminalReason.SUCCESS,
                "terminal_at": record.created_at,
                "cleanup_due_at": record.created_at,
                "cleanup_failure_reason": "cleanup_authority_blocked",
            }
        )
    )

    await orchestrator.delete_sandbox(sandbox.id)

    stored = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)

    assert stored is not None
    assert stored.state.value == "cleaned"
    assert stored.cleanup_state.value == "completed"


@pytest.mark.asyncio
async def test_delete_reclaimable_sandbox_publishes_lease_expiry_final_truth(tmp_path) -> None:
    sandbox_id = "sandbox-rock-2d"
    compose_project = "orket-sandbox-rock-2d"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-2d",
        down_returncode=1,
    )
    orchestrator = _orchestrator(tmp_path, runner)

    sandbox = await orchestrator.create_sandbox(
        rock_id="rock-2d",
        project_name="Reclaimable Cleanup Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
    assert record is not None
    await orchestrator.lifecycle_service.repository.save_record(
        record.model_copy(
            update={
                "state": SandboxState.RECLAIMABLE,
                "record_version": record.record_version + 1,
                "terminal_reason": TerminalReason.LEASE_EXPIRED,
                "terminal_at": record.created_at,
                "cleanup_due_at": record.created_at,
            }
        )
    )

    await orchestrator.delete_sandbox(sandbox.id)

    stored = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
    final_truth = await orchestrator.control_plane_repository.get_final_truth(run_id="rock-2d")
    events = await orchestrator.lifecycle_service.repository.list_events(sandbox.id)

    assert stored is not None
    assert stored.state.value == "cleaned"
    assert stored.required_evidence_ref is not None
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.BLOCKED
    assert final_truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP
    assert any(event.event_type == "sandbox.policy_terminal_outcome" for event in events)


@pytest.mark.asyncio
async def test_delete_sandbox_fails_closed_when_cleanup_observation_is_unavailable(tmp_path) -> None:
    sandbox_id = "sandbox-rock-2c"
    compose_project = "orket-sandbox-rock-2c"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-2c",
    )
    orchestrator = _orchestrator(tmp_path, runner)

    await orchestrator.create_sandbox(
        rock_id="rock-2c",
        project_name="Cleanup Observation Failure Sandbox",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(tmp_path),
    )
    runner.list_returncode = 1

    with pytest.raises(RuntimeError, match="Failed to observe sandbox resources before cleanup"):
        await orchestrator.delete_sandbox(sandbox_id)

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)

    assert record is not None
    assert record.state.value == "terminal"
    assert record.cleanup_state.value == "failed"
    assert "Failed to observe container resources" in str(record.cleanup_last_error or "")


@pytest.mark.asyncio
async def test_create_sandbox_fails_closed_before_docker_when_lifecycle_store_is_unavailable(tmp_path, monkeypatch) -> None:
    sandbox_id = "sandbox-rock-3"
    compose_project = "orket-sandbox-rock-3"
    runner = FakeLifecycleRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="rock-3")
    orchestrator = _orchestrator(tmp_path, runner)

    async def _raise_store_unavailable(**_kwargs):
        raise OSError("sandbox lifecycle store unavailable")

    monkeypatch.setattr(orchestrator.lifecycle_service, "create_record", _raise_store_unavailable)

    with pytest.raises(OSError, match="store unavailable"):
        await orchestrator.create_sandbox(
            rock_id="rock-3",
            project_name="Store Outage",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

    assert runner.async_calls == []
    assert orchestrator.registry.get(sandbox_id) is None
    assert sandbox_id not in orchestrator.registry.port_allocator.allocated_ports


@pytest.mark.asyncio
async def test_create_sandbox_releases_active_lease_when_create_record_fails_after_lease_publish(
    tmp_path,
    monkeypatch,
) -> None:
    sandbox_id = "sandbox-rock-3b"
    compose_project = "orket-sandbox-rock-3b"
    runner = FakeLifecycleRunner(compose_project=compose_project, sandbox_id=sandbox_id, run_id="rock-3b")
    orchestrator = _orchestrator(tmp_path, runner)

    async def _publish_lease_then_fail(**kwargs):
        source_reservation_id = str(kwargs["source_reservation_id"])
        await orchestrator.control_plane_publication.publish_lease(
            lease_id=orchestrator.control_plane_reservations.lease_id_for_sandbox(sandbox_id),
            resource_id=f"sandbox-allocation:{sandbox_id}",
            holder_ref="sandbox-run:rock-3b",
            lease_epoch=1,
            publication_timestamp="2026-03-26T12:00:00+00:00",
            expiry_basis="sandbox_lifecycle_record_creation_started",
            status=LeaseStatus.ACTIVE,
            cleanup_eligibility_rule="sandbox_cleanup_post_terminal",
            source_reservation_id=source_reservation_id,
        )
        raise OSError("sandbox lifecycle store unavailable after lease publication")

    monkeypatch.setattr(orchestrator.lifecycle_service, "create_record", _publish_lease_then_fail)

    with pytest.raises(OSError, match="store unavailable after lease publication"):
        await orchestrator.create_sandbox(
            rock_id="rock-3b",
            project_name="Store Outage After Lease",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

    reservation = await orchestrator.control_plane_repository.get_latest_reservation_record(
        reservation_id=f"sandbox-reservation:{sandbox_id}"
    )
    lease = await orchestrator.control_plane_repository.get_latest_lease_record(
        lease_id=f"sandbox-lease:{sandbox_id}"
    )

    assert reservation is not None
    assert reservation.status is ReservationStatus.INVALIDATED
    assert lease is not None
    assert lease.status is LeaseStatus.RELEASED
    assert runner.async_calls == []
    assert orchestrator.registry.get(sandbox_id) is None
    assert sandbox_id not in orchestrator.registry.port_allocator.allocated_ports


@pytest.mark.asyncio
async def test_create_sandbox_terminalizes_when_initial_runtime_never_reaches_running_state(tmp_path) -> None:
    sandbox_id = "sandbox-rock-4"
    compose_project = "orket-sandbox-rock-4"
    runner = FakeLifecycleRunner(
        compose_project=compose_project,
        sandbox_id=sandbox_id,
        run_id="rock-4",
        container_state="restarting",
    )
    orchestrator = _orchestrator(tmp_path, runner)
    orchestrator._initial_health_attempts = 2
    orchestrator._initial_health_delay_seconds = 0.0

    with pytest.raises(RuntimeError, match="startup health verification failed"):
        await orchestrator.create_sandbox(
            rock_id="rock-4",
            project_name="Broken Startup",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

    record = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
    final_truth = await orchestrator.control_plane_repository.get_final_truth(run_id="rock-4")
    events = await orchestrator.lifecycle_service.repository.list_events(sandbox_id)

    assert record is not None
    assert record.state.value == "terminal"
    assert record.terminal_reason.value == "start_failed"
    assert record.cleanup_due_at is not None
    assert record.required_evidence_ref is not None
    assert final_truth is not None
    assert final_truth.result_class is ResultClass.FAILED
    assert final_truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION
    assert any(event.event_type == "sandbox.lifecycle_terminal_outcome" for event in events)
