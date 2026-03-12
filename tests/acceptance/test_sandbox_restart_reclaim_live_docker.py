# Layer: end-to-end

from __future__ import annotations

import asyncio
import json
import os
import shutil

import pytest

from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.acceptance._sandbox_live_ports import patch_orchestrator_port_allocator


pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


def _unhealthy_compose(sandbox, _db_password: str) -> str:
    return f"""services:
  api:
    image: nginx:alpine
    labels:
      orket.managed: "true"
      orket.sandbox_id: "{sandbox.id}"
      orket.run_id: "{sandbox.rock_id}"
    healthcheck:
      test: ["CMD-SHELL", "exit 1"]
      interval: 1s
      timeout: 1s
      retries: 1
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
async def test_live_unhealthy_policy_terminalizes_restart_loop_and_projects_diagnostics(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _unhealthy_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)
    policy = SandboxLifecyclePolicy(restart_threshold_count=9, restart_window_seconds=60, unhealthy_duration_seconds=1)
    orchestrator.lifecycle_service.policy = policy
    orchestrator.restart_policy.policy = policy

    compose_project = "orket-sandbox-live-restart-policy-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    sandbox = None
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-restart-policy-1",
            project_name="Live Restart Policy",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

        record = None
        for _ in range(12):
            await orchestrator.health_check(sandbox.id)
            record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
            if record and record.state is SandboxState.TERMINAL:
                break
            await asyncio.sleep(0.5)

        views = await orchestrator.list_sandboxes()

        assert record is not None
        assert record.state is SandboxState.TERMINAL
        assert record.terminal_reason is TerminalReason.RESTART_LOOP
        assert views[0]["restart_summary"]["terminal_reason"] == "restart_loop"

        await orchestrator.delete_sandbox(sandbox.id)
    finally:
        await _compose_cleanup(compose_path, compose_project)


@pytest.mark.asyncio
async def test_live_reclaimable_sandbox_can_be_reacquired_and_stale_owner_cannot_renew(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    db_path = str(tmp_path / "sandbox_lifecycle.db")
    orchestrator_a = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=db_path,
    )
    orchestrator_b = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=db_path,
    )
    monkeypatch.setattr(orchestrator_a, "_generate_compose_file", _lightweight_compose)
    monkeypatch.setattr(orchestrator_b, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator_a, monkeypatch)
    patch_orchestrator_port_allocator(orchestrator_b, monkeypatch)
    orchestrator_a.instance_id = "runner-a"
    orchestrator_a.lifecycle_service.instance_id = "runner-a"
    orchestrator_b.instance_id = "runner-b"
    orchestrator_b.lifecycle_service.instance_id = "runner-b"

    compose_project = "orket-sandbox-live-reclaim-1"
    compose_path = str(orchestrator_a._compose_path(str(tmp_path)))
    sandbox = None
    try:
        sandbox = await orchestrator_a.create_sandbox(
            rock_id="live-reclaim-1",
            project_name="Live Reclaim",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        record = await orchestrator_a.lifecycle_service.repository.get_record(sandbox.id)
        assert record is not None
        await orchestrator_a.lifecycle_service.repository.save_record(
            record.model_copy(
                update={
                    "record_version": record.record_version + 1,
                    "lease_expires_at": "2026-03-01T00:00:00+00:00",
                }
            )
        )

        reclaimable = await orchestrator_a.reconcile_sandbox(sandbox.id)
        reacquired = await orchestrator_b.reacquire_sandbox_ownership(sandbox.id)
        before = await orchestrator_b.lifecycle_service.repository.get_record(sandbox.id)
        stale_health = await orchestrator_a.health_check(sandbox.id)
        after = await orchestrator_b.lifecycle_service.repository.get_record(sandbox.id)

        assert reclaimable["state"] == "reclaimable"
        assert reacquired["state"] == "active"
        assert reacquired["owner_instance_id"] == "runner-b"
        assert stale_health is False
        assert before is not None and after is not None
        assert after.owner_instance_id == "runner-b"
        assert after.lease_epoch == before.lease_epoch

        await orchestrator_b.delete_sandbox(sandbox.id)
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )
        assert containers == []
    finally:
        await _compose_cleanup(compose_path, compose_project)
