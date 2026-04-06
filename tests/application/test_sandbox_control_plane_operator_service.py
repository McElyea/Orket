# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_operator_service import SandboxControlPlaneOperatorService
from orket.core.domain import OperatorCommandClass
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository

pytestmark = pytest.mark.unit


def _record(*, state: SandboxState, record_version: int) -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        owner_instance_id="runner-a",
        lease_epoch=1,
        lease_expires_at="2026-03-24T01:05:00+00:00",
        state=state,
        cleanup_state=CleanupState.NONE if state is not SandboxState.CLEANED else CleanupState.COMPLETED,
        record_version=record_version,
        created_at="2026-03-24T01:00:00+00:00",
        last_heartbeat_at="2026-03-24T01:01:00+00:00",
        terminal_at="2026-03-24T01:02:00+00:00" if state in {SandboxState.TERMINAL, SandboxState.CLEANED} else None,
        terminal_reason=TerminalReason.CANCELED if state in {SandboxState.TERMINAL, SandboxState.CLEANED} else None,
        cleanup_due_at="2026-03-24T01:12:00+00:00" if state in {SandboxState.TERMINAL, SandboxState.CLEANED} else None,
        cleanup_attempts=1 if state is SandboxState.CLEANED else 0,
        required_evidence_ref="evidence/sb-1.json" if state in {SandboxState.TERMINAL, SandboxState.CLEANED} else None,
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


@pytest.mark.asyncio
async def test_sandbox_operator_service_publishes_cancel_run_command() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneOperatorService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    action = await service.publish_cancel_run_action(
        actor_ref="api_key_fingerprint:sha256:test",
        before_record=_record(state=SandboxState.ACTIVE, record_version=3),
        after_record=_record(state=SandboxState.CLEANED, record_version=7),
        final_truth=None,
    )

    stored = await repository.get_operator_action(action_id=action.action_id)

    assert stored is not None
    assert stored.command_class is OperatorCommandClass.CANCEL_RUN
    assert stored.target_ref == "run-1"
    assert stored.affected_resource_refs == ["sandbox-scope:sb-1"]
    assert stored.receipt_refs == ["evidence/sb-1.json"]
