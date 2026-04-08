from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import CheckpointRecord
from orket.core.domain import CheckpointResumabilityClass

pytestmark = pytest.mark.integration


def _checkpoint() -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-recovery-1",
        parent_ref="attempt-recovery-1",
        creation_timestamp="2026-04-07T00:00:00+00:00",
        state_snapshot_ref="snapshot-recovery-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:recovery-1"],
        dependent_effect_refs=["effect-recovery-1"],
        policy_digest="sha256:policy-recovery-1",
        integrity_verification_ref="integrity-recovery-1",
    )


@pytest.mark.asyncio
async def test_published_checkpoint_survives_repository_reconstruction(tmp_path: Path) -> None:
    """Layer: integration. Verifies checkpoint publication is durable across a crash-recovery-style reopen."""
    db_path = tmp_path / "control-plane.sqlite3"
    service = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(db_path))
    checkpoint = await service.publish_checkpoint(checkpoint=_checkpoint())

    recovered_repository = AsyncControlPlaneRecordRepository(db_path)
    loaded = await recovered_repository.get_checkpoint(checkpoint_id=checkpoint.checkpoint_id)
    listed = await recovered_repository.list_checkpoints(parent_ref=checkpoint.parent_ref)

    assert loaded == checkpoint
    assert listed == [checkpoint]
