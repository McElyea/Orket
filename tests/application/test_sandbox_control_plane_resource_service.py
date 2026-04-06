# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_resource_service import (
    SandboxControlPlaneResourceService,
)
from orket.core.contracts import LeaseRecord
from orket.core.domain import CleanupAuthorityClass, LeaseStatus, OrphanClassification, OwnershipClass
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository

pytestmark = pytest.mark.unit


def _record(**overrides) -> SandboxLifecycleRecord:
    payload = {
        "sandbox_id": "sb-1",
        "compose_project": "orket-sandbox-sb-1",
        "workspace_path": "workspace/sb-1",
        "run_id": "run-1",
        "owner_instance_id": "runner-a",
        "lease_epoch": 2,
        "lease_expires_at": "2026-03-27T01:05:00+00:00",
        "state": SandboxState.ACTIVE,
        "cleanup_state": CleanupState.NONE,
        "record_version": 4,
        "created_at": "2026-03-27T01:00:00+00:00",
        "last_heartbeat_at": "2026-03-27T01:00:30+00:00",
        "cleanup_attempts": 0,
        "managed_resource_inventory": ManagedResourceInventory(),
        "requires_reconciliation": False,
        "docker_context": "desktop-linux",
        "docker_host_id": "host-a",
    }
    payload.update(overrides)
    return SandboxLifecycleRecord(**payload)


@pytest.mark.asyncio
async def test_sandbox_control_plane_resource_service_publishes_active_resource_truth() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneResourceService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    published = await service.publish_from_record(
        record=_record(),
        observed_at="2026-03-27T01:00:30+00:00",
    )

    assert published.resource_id == "sandbox-scope:sb-1"
    assert published.resource_kind == "sandbox_runtime"
    assert published.namespace_scope == "sandbox-scope:sb-1"
    assert published.ownership_class is OwnershipClass.RUN_OWNED
    assert published.cleanup_authority_class is CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION
    assert published.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert published.provenance_ref == "sandbox-lifecycle:sb-1:active:4"


@pytest.mark.asyncio
async def test_sandbox_control_plane_resource_service_marks_lost_runtime_as_suspected_orphan() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneResourceService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    published = await service.publish_from_record(
        record=_record(
            state=SandboxState.TERMINAL,
            cleanup_state=CleanupState.NONE,
            terminal_reason=TerminalReason.LOST_RUNTIME,
            requires_reconciliation=True,
        ),
        observed_at="2026-03-27T01:10:00+00:00",
    )

    assert published.ownership_class is OwnershipClass.RUN_OWNED
    assert published.cleanup_authority_class is CleanupAuthorityClass.RUNTIME_CLEANUP_AFTER_RECONCILIATION
    assert published.orphan_classification is OrphanClassification.SUSPECTED_ORPHAN
    assert published.reconciliation_status == "reconciliation_required"


@pytest.mark.asyncio
async def test_sandbox_control_plane_resource_service_publishes_pre_lifecycle_closeout() -> None:
    repository = InMemoryControlPlaneRecordRepository()
    service = SandboxControlPlaneResourceService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    published = await service.publish_from_lease_closeout(
        sandbox_id="sb-1",
        lease=LeaseRecord(
            lease_id="sandbox-lease:sb-1",
            resource_id="sandbox-scope:sb-1",
            holder_ref="sandbox-instance:runner-a",
            lease_epoch=1,
            granted_timestamp="2026-03-27T01:00:00+00:00",
            publication_timestamp="2026-03-27T01:00:05+00:00",
            expiry_basis="sandbox_create_record_failed",
            status=LeaseStatus.RELEASED,
            last_confirmed_observation="sandbox-lifecycle:sb-1:creating:1",
            cleanup_eligibility_rule="sandbox_cleanup_policy:v1",
        ),
        observed_at="2026-03-27T01:00:05+00:00",
        closeout_basis="sandbox_create_record_failed",
    )

    assert published.resource_id == "sandbox-scope:sb-1"
    assert published.resource_kind == "sandbox_runtime"
    assert published.namespace_scope == "sandbox-scope:sb-1"
    assert published.ownership_class is OwnershipClass.RUN_OWNED
    assert published.cleanup_authority_class is CleanupAuthorityClass.ADAPTER_CLEANUP_ONLY
    assert published.orphan_classification is OrphanClassification.NOT_ORPHANED
    assert published.current_observed_state.startswith("lease_status:lease_released;")
    assert published.reconciliation_status == "lifecycle_record_unavailable"
