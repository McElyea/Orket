# Layer: integration

from __future__ import annotations

from orket.application.services.sandbox_cleanup_verification_service import SandboxCleanupVerificationService
from orket.core.domain.sandbox_cleanup import DockerResourceType, ObservedDockerResource
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


def _record() -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        lease_epoch=0,
        state=SandboxState.TERMINAL,
        cleanup_state=CleanupState.IN_PROGRESS,
        record_version=3,
        created_at="2026-03-11T00:00:00+00:00",
        terminal_reason="failed",
        cleanup_attempts=0,
        managed_resource_inventory=ManagedResourceInventory(
            containers=["sb-1-api", "sb-1-frontend"],
            networks=["sb-1-net"],
            managed_volumes=["sb-1-db"],
        ),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


def _resource(resource_type: DockerResourceType, name: str, labels: dict[str, str] | None = None) -> ObservedDockerResource:
    return ObservedDockerResource(
        resource_type=resource_type,
        name=name,
        docker_context="desktop-linux",
        docker_host_id="host-a",
        labels=labels or {},
    )


def test_cleanup_verification_detects_partial_cleanup_and_unexpected_managed_resources() -> None:
    service = SandboxCleanupVerificationService()
    result = service.verify_absence(
        record=_record(),
        observed_resources=[
            _resource(DockerResourceType.CONTAINER, "sb-1-api"),
            _resource(
                DockerResourceType.CONTAINER,
                "sb-1-extra",
                labels={"orket.managed": "true", "orket.sandbox_id": "sb-1", "orket.run_id": "run-1"},
            ),
        ],
    )

    assert result.success is False
    assert result.remaining_expected == ["sb-1-api"]
    assert result.unexpected_managed_present == ["sb-1-extra"]


def test_cleanup_verification_marks_success_when_observation_is_complete_and_inventory_is_absent() -> None:
    service = SandboxCleanupVerificationService()
    result = service.verify_absence(record=_record(), observed_resources=[])

    assert result.success is True
    assert result.remaining_expected == []
    assert result.absent_expected == ["sb-1-api", "sb-1-db", "sb-1-frontend", "sb-1-net"]
    assert result.observation_complete is True


def test_cleanup_verification_blocks_success_when_observation_is_incomplete() -> None:
    service = SandboxCleanupVerificationService()
    result = service.verify_absence(record=_record(), observed_resources=[], observation_complete=False)

    assert result.success is False
    assert result.observation_complete is False
    assert result.unverified_expected == ["sb-1-api", "sb-1-db", "sb-1-frontend", "sb-1-net"]
    assert result.absent_expected == []
