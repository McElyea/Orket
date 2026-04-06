# Layer: end-to-end

from __future__ import annotations

import asyncio
import json
import os
import shutil

import pytest

from orket.adapters.storage.command_runner import CommandRunner
from orket.core.domain.sandbox import SandboxRegistry, TechStack
from orket.core.domain.sandbox_lifecycle import CleanupState, LifecycleEvent, SandboxState, TerminalReason
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.acceptance._sandbox_live_ports import patch_orchestrator_port_allocator

pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


class FailAfterCreateIntentRunner(CommandRunner):
    def __init__(self) -> None:
        self._failed = False

    async def run_async(self, *cmd: str):
        if not self._failed and cmd[:2] == ("docker-compose", "-f") and "ps" in cmd and "-q" in cmd:
            self._failed = True
            raise OSError("induced ambiguous create outcome")
        return await super().run_async(*cmd)


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
async def test_live_unknown_outcome_reconciliation_recovers_to_active(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        command_runner=FailAfterCreateIntentRunner(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)
    sandbox_id = orchestrator.sandbox_policy_node.build_sandbox_id("live-unknown-1")
    compose_project = orchestrator.sandbox_policy_node.build_compose_project(sandbox_id)
    compose_path = str(orchestrator._compose_path(str(tmp_path)))

    try:
        with pytest.raises(OSError, match="ambiguous create outcome"):
            await orchestrator.create_sandbox(
                rock_id="live-unknown-1",
                project_name="Live Unknown Outcome",
                tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
                workspace_path=str(tmp_path),
            )

        blocked = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
        assert blocked is not None
        assert blocked.state is SandboxState.STARTING
        assert blocked.requires_reconciliation is True

        await orchestrator.reconcile_sandbox(sandbox_id)

        reconciled = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
        assert reconciled is not None
        assert reconciled.state is SandboxState.ACTIVE
        assert reconciled.requires_reconciliation is False
        assert reconciled.managed_resource_inventory.containers

        await orchestrator.delete_sandbox(sandbox_id)
        cleaned = await orchestrator.lifecycle_service.repository.get_record(sandbox_id)
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )

        assert cleaned is not None
        assert cleaned.state is SandboxState.CLEANED
        assert containers == []
    finally:
        await _compose_cleanup(compose_path, compose_project)


@pytest.mark.asyncio
async def test_live_cleanup_sweeper_cleans_due_terminal_sandbox(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)

    compose_project = "orket-sandbox-live-sweeper-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    sandbox = None
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-sweeper-1",
            project_name="Live Sweeper",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        record = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        assert record is not None
        await orchestrator.lifecycle_service.repository.save_record(
            record.model_copy(
                update={
                    "state": SandboxState.TERMINAL,
                    "cleanup_state": CleanupState.SCHEDULED,
                    "record_version": record.record_version + 1,
                    "terminal_reason": TerminalReason.SUCCESS,
                    "terminal_at": record.created_at,
                    "cleanup_due_at": record.created_at,
                }
            )
        )

        swept = await orchestrator.sweep_due_cleanups(max_records=1)
        cleaned = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )

        assert len(swept) == 1
        assert cleaned is not None
        assert cleaned.state is SandboxState.CLEANED
        assert cleaned.cleanup_state is CleanupState.COMPLETED
        assert orchestrator.registry.get(sandbox.id) is None
        assert containers == []
    finally:
        await _compose_cleanup(compose_path, compose_project)


@pytest.mark.asyncio
async def test_live_reconciliation_recovers_after_crash_between_delete_and_verify(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", _lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)

    compose_project = "orket-sandbox-live-crash-recovery-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    sandbox = None
    original_transition = orchestrator.lifecycle_service.mutations.transition_state

    async def crash_on_cleanup_complete(**kwargs):
        if kwargs.get("event") is LifecycleEvent.CLEANUP_VERIFIED_COMPLETE:
            raise RuntimeError("simulated crash after delete")
        return await original_transition(**kwargs)

    monkeypatch.setattr(orchestrator.lifecycle_service.mutations, "transition_state", crash_on_cleanup_complete)
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-crash-recovery-1",
            project_name="Live Crash Recovery",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )

        with pytest.raises(RuntimeError, match="simulated crash after delete"):
            await orchestrator.delete_sandbox(sandbox.id)

        blocked = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        assert blocked is not None
        assert blocked.state is SandboxState.TERMINAL
        assert blocked.cleanup_state is CleanupState.IN_PROGRESS

        await orchestrator.reconcile_sandbox(sandbox.id)

        cleaned = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        containers = await _docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        )

        assert cleaned is not None
        assert cleaned.state is SandboxState.CLEANED
        assert cleaned.terminal_reason is TerminalReason.CLEANED_EXTERNALLY
        assert orchestrator.registry.get(sandbox.id) is None
        assert containers == []
    finally:
        await _compose_cleanup(compose_path, compose_project)
