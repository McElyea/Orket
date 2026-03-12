# Layer: end-to-end

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import aiofiles
import pytest

from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.domain.sandbox import SandboxRegistry, TechStack
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from tests.acceptance._sandbox_live_common import compose_cleanup, docker_rows, lightweight_compose
from tests.acceptance._sandbox_live_ports import patch_orchestrator_port_allocator


pytestmark = pytest.mark.skipif(
    os.getenv("ORKET_RUN_SANDBOX_ACCEPTANCE") != "1",
    reason="Set ORKET_RUN_SANDBOX_ACCEPTANCE=1 to run live sandbox acceptance tests.",
)


@pytest.mark.asyncio
async def test_live_terminal_evidence_export_and_sweeper_cleanup(tmp_path, monkeypatch) -> None:
    if shutil.which("docker-compose") is None or shutil.which("docker") is None:
        pytest.skip("docker tooling is unavailable")

    orchestrator = SandboxOrchestrator(
        workspace_root=tmp_path,
        registry=SandboxRegistry(),
        lifecycle_db_path=str(tmp_path / "sandbox_lifecycle.db"),
    )
    monkeypatch.setattr(orchestrator, "_generate_compose_file", lightweight_compose)
    patch_orchestrator_port_allocator(orchestrator, monkeypatch)
    orchestrator.lifecycle_service.policy = SandboxLifecyclePolicy(ttl_success_minutes=0)
    orchestrator.lifecycle_service.terminal_evidence = SandboxTerminalEvidenceService(
        evidence_root=tmp_path / "terminal_evidence"
    )

    compose_project = "orket-sandbox-live-evidence-cleanup-1"
    compose_path = str(orchestrator._compose_path(str(tmp_path)))
    sandbox = None
    try:
        sandbox = await orchestrator.create_sandbox(
            rock_id="live-evidence-cleanup-1",
            project_name="Live Evidence Cleanup",
            tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
            workspace_path=str(tmp_path),
        )
        terminal = await orchestrator.lifecycle_service.terminal_outcomes.record_workflow_terminal_outcome(
            sandbox_id=sandbox.id,
            terminal_reason=TerminalReason.SUCCESS,
            evidence_payload={"kind": "live_report", "status": "success"},
            operation_id_prefix="workflow-finish",
            expected_owner_instance_id=orchestrator.lifecycle_service.instance_id,
            expected_lease_epoch=1,
            terminal_at="2026-03-11T00:10:00+00:00",
        )
        scheduled = await orchestrator.reconcile_sandbox(sandbox.id)
        previews = await orchestrator.lifecycle_recovery.preview_due_cleanups(max_records=1)
        swept = await orchestrator.sweep_due_cleanups(max_records=1)
        cleaned = await orchestrator.lifecycle_service.repository.get_record(sandbox.id)
        events = await orchestrator.lifecycle_service.repository.list_events(sandbox.id)

        assert terminal.state is SandboxState.TERMINAL
        assert scheduled["cleanup_state"] == "scheduled"
        assert previews[0]["reason_code"] == "success"
        assert previews[0]["policy_match"] == "terminal_cleanup_due"
        assert previews[0]["dry_run"] is True
        assert previews[0]["cleanup_result"] == "would_execute_compose"
        assert len(swept) == 1
        assert cleaned is not None
        assert cleaned.state is SandboxState.CLEANED
        assert cleaned.cleanup_state is CleanupState.COMPLETED
        assert cleaned.required_evidence_ref is not None
        async with aiofiles.open(Path(cleaned.required_evidence_ref), "r", encoding="utf-8") as handle:
            evidence = json.loads(await handle.read())
        assert evidence["payload"]["kind"] == "live_report"
        assert any(event.event_type == "sandbox.workflow_terminal_outcome" for event in events)
        assert any(event.event_type == "sandbox.cleanup_decision_evaluated" for event in events)
        assert any(event.event_type == "sandbox.cleanup_execution_result" for event in events)
        assert await docker_rows(
            "docker",
            "ps",
            "-a",
            "--filter",
            f"label=com.docker.compose.project={compose_project}",
            "--format",
            "{{json .}}",
        ) == []
    finally:
        await compose_cleanup(compose_path, compose_project)
