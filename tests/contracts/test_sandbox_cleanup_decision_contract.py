# Layer: contract

from __future__ import annotations

from orket.application.services.sandbox_cleanup_authority_service import CleanupAuthorityDecision
from orket.application.services.sandbox_cleanup_decision_service import SandboxCleanupDecisionService
from orket.core.domain.sandbox_cleanup import DockerResourceType, ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


class _Publisher:
    async def emit(self, **_kwargs) -> str:
        return "primary"


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 1,
        "lease_expires_at": "2026-03-11T00:05:00+00:00",
        "state": SandboxState.TERMINAL,
        "cleanup_state": CleanupState.SCHEDULED,
        "record_version": 3,
        "created_at": "2026-03-11T00:00:00+00:00",
        "terminal_at": "2026-03-11T00:00:00+00:00",
        "terminal_reason": TerminalReason.SUCCESS,
        "cleanup_due_at": "2026-03-11T00:15:00+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


def test_cleanup_decision_payload_exposes_required_reason_policy_and_mode_fields(tmp_path) -> None:
    compose_path = tmp_path / "docker-compose.sandbox.yml"
    compose_path.touch()
    service = SandboxCleanupDecisionService(event_publisher=_Publisher())

    decision = service.build_decision(
        record=_record(),
        compose_path=compose_path,
        observed_resources=[
            ObservedDockerResource(
                resource_type=DockerResourceType.CONTAINER,
                name="orket-sandbox-sb-1-api-1",
                docker_context="desktop-linux",
                docker_host_id="host-a",
                labels={"orket.managed": "true", "orket.sandbox_id": "sb-1", "orket.run_id": "run-1"},
            )
        ],
        authority=CleanupAuthorityDecision(
            compose_cleanup_allowed=True,
            fallback_resource_names=["orket-sandbox-sb-1-api-1"],
            blocked_resource_names=[],
            reason_codes=["compose_project_authority"],
        ),
        dry_run=True,
    )

    payload = decision.to_payload()

    assert payload["reason_code"] == "success"
    assert payload["policy_match"] == "terminal_cleanup_due"
    assert payload["dry_run"] is True
    assert payload["cleanup_result"] == "would_execute_compose"
    assert payload["cleanup_strategy"] == "compose"
    assert payload["authority_reason_codes"] == ["compose_project_authority"]
