# Layer: end-to-end

from __future__ import annotations

import asyncio
import json
import os
import shutil

import pytest

from orket.core.domain import LeaseStatus, ReservationStatus
from orket.core.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.acceptance._sandbox_live_ports import patch_orchestrator_port_allocator

pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


def _lightweight_compose(sandbox, _db_password: str) -> str:
    return f"""services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    ports:
      - "{sandbox.ports.api}:80"
    volumes:
      - sandbox-data:/usr/share/nginx/html
volumes:
  sandbox-data:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
networks:
  default:
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
"""


async def _docker_rows(*cmd: str) -> list[dict[str, object]]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    rows: list[dict[str, object]] = []
    for line in stdout.decode().splitlines():
        token = line.strip()
        if token:
            rows.append(json.loads(token))
    return rows


async def _compose_cleanup(compose_path: str, compose_project: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "docker-compose",
        "-f",
        compose_path,
        "-p",
        compose_project,
        "down",
        "-v",
        "--remove-orphans",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()


@pytest.mark.asyncio
async def test_live_create_health_and_cleanup_flow(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)

    sandbox = None
    compose_project = "orket-sandbox-live-cleanup-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-cleanup-1",
            project_name="Live Cleanup",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        active_reservation = await orchestrator.control_plane_repository.get_latest_reservation_record(
            reservation_id=f"sandbox-reservation:{sandbox.id}"
        )
        reservation_history = await orchestrator.control_plane_repository.list_reservation_records(
            reservation_id=f"sandbox-reservation:{sandbox.id}"
        )
        active_lease = await orchestrator.control_plane_repository.get_latest_lease_record(
            lease_id=f"sandbox-lease:{sandbox.id}"
        )
        active_journal = await orchestrator.control_plane_repository.list_effect_journal_entries(run_id="live-cleanup-1")
        active_views = await orchestrator.list_sandboxes()
        assert sandbox.status.value == "running"
        assert record is not None
        assert record.state.value == "active"
        assert record.managed_resource_inventory.containers
        assert active_reservation is not None
        assert active_reservation.status is ReservationStatus.PROMOTED_TO_LEASE
        assert [record.status for record in reservation_history] == [
            ReservationStatus.ACTIVE,
            ReservationStatus.PROMOTED_TO_LEASE,
        ]
        assert active_lease is not None
        assert active_lease.status is LeaseStatus.ACTIVE
        assert active_lease.source_reservation_id == active_reservation.reservation_id
        assert [entry.effect_id for entry in active_journal] == [
            f"sandbox-effect:{sandbox.id}:deploy:lease_epoch:00000001"
        ]
        assert active_views[0]["control_plane_run_state"] == "executing"
        assert active_views[0]["control_plane_current_attempt_state"] == "attempt_executing"
        assert active_views[0]["control_plane_recovery_decision_id"] is None
        assert active_views[0]["control_plane_checkpoint_id"] is None
        assert active_views[0]["control_plane_checkpoint_resumability_class"] is None
        assert active_views[0]["control_plane_checkpoint_acceptance_outcome"] is None
        assert active_views[0]["control_plane_reservation_status"] == "reservation_promoted_to_lease"
        assert active_views[0]["control_plane_lease_status"] == "lease_active"
        assert active_views[0]["control_plane_final_result_class"] is None
        assert active_views[0]["control_plane_final_closure_basis"] is None
        assert active_views[0]["operator_action_count"] == 0
        assert await orchestrator.health_check(sandbox.id) is True

        await orchestrator.delete_sandbox(sandbox.id, operator_actor_ref="operator:live-cleanup")

        cleaned = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        released_lease = await orchestrator.control_plane_repository.get_latest_lease_record(
            lease_id=f"sandbox-lease:{sandbox.id}"
        )
        lease_history = await orchestrator.control_plane_repository.list_lease_records(
            lease_id=f"sandbox-lease:{sandbox.id}"
        )
        operator_actions = await orchestrator.control_plane_repository.list_operator_actions(
            target_ref="live-cleanup-1"
        )
        journal_entries = await orchestrator.control_plane_repository.list_effect_journal_entries(run_id="live-cleanup-1")
        cleaned_views = await orchestrator.list_sandboxes()
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )
        networks = await _docker_rows(
            "docker",
            "network",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )
        volumes = await _docker_rows(
            "docker",
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )

        assert cleaned is not None
        assert cleaned.state.value == "cleaned"
        assert cleaned.cleanup_state.value == "completed"
        assert released_lease is not None
        assert released_lease.status is LeaseStatus.RELEASED
        assert {record.status for record in lease_history} >= {
            LeaseStatus.PENDING,
            LeaseStatus.ACTIVE,
            LeaseStatus.RELEASED,
        }
        assert len(operator_actions) == 1
        assert operator_actions[0].actor_ref == "operator:live-cleanup"
        assert cleaned_views[0]["control_plane_run_state"] == "cancelled"
        assert cleaned_views[0]["control_plane_current_attempt_state"] == "attempt_abandoned"
        assert cleaned_views[0]["control_plane_recovery_decision_id"] is None
        assert cleaned_views[0]["control_plane_checkpoint_id"] is None
        assert cleaned_views[0]["control_plane_checkpoint_resumability_class"] is None
        assert cleaned_views[0]["control_plane_checkpoint_acceptance_outcome"] is None
        assert cleaned_views[0]["control_plane_reservation_status"] == "reservation_promoted_to_lease"
        assert cleaned_views[0]["control_plane_lease_status"] == "lease_released"
        assert cleaned_views[0]["control_plane_final_result_class"] == "blocked"
        assert cleaned_views[0]["control_plane_final_closure_basis"] == "cancelled_by_authority"
        assert cleaned_views[0]["operator_action_count"] == 1
        assert [entry.effect_id for entry in journal_entries] == [
            f"sandbox-effect:{sandbox.id}:deploy:lease_epoch:00000001",
            f"sandbox-effect:{sandbox.id}:cleanup:lease_epoch:00000001",
        ]
        assert containers == []
        assert networks == []
        assert volumes == []
    finally:
        await _compose_cleanup(compose_path, compose_project)


@pytest.mark.asyncio
async def test_live_cleanup_rejects_host_context_mismatch(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)

    compose_project = "orket-sandbox-live-mismatch-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    sandbox = None
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-mismatch-1",
            project_name="Live Mismatch",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        assert record is not None
        await orchestrator.lifecycle_service.repository.save_record(
            record.model_copy(update={"docker_host_id": "foreign-host"})
        )

        with pytest.raises(RuntimeError, match="Cleanup authority blocked"):
            await orchestrator.delete_sandbox(sandbox.id)

        blocked = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )

        assert blocked is not None
        assert blocked.state.value == "terminal"
        assert blocked.cleanup_state.value == "failed"
        assert containers != []
    finally:
        await _compose_cleanup(compose_path, compose_project)
