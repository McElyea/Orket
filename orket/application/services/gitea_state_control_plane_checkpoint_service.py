from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.gitea_state_control_plane_execution_service import (
    GiteaStateControlPlaneExecutionService,
)
from orket.core.contracts import AttemptRecord, CheckpointAcceptanceRecord, CheckpointRecord, RunRecord
from orket.core.domain import CheckpointReobservationClass, CheckpointResumabilityClass
from orket.runtime_paths import resolve_control_plane_db_path


class GiteaStateControlPlaneCheckpointError(ValueError):
    """Raised when Gitea worker checkpoint authority cannot be published truthfully."""


class GiteaStateControlPlaneCheckpointService:
    """Publishes pre-effect Gitea worker checkpoints from claimed-card observations."""

    def __init__(self, *, publication: ControlPlanePublicationService) -> None:
        self.publication = publication

    async def publish_pre_effect_checkpoint(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        card_id: str,
        from_state: str,
        lease_observation: Mapping[str, object],
    ) -> tuple[CheckpointRecord, CheckpointAcceptanceRecord]:
        checkpoint_id = self.checkpoint_id_for(attempt_id=attempt.attempt_id)
        existing_checkpoint = await self.publication.repository.get_checkpoint(checkpoint_id=checkpoint_id)
        if existing_checkpoint is None:
            checkpoint = await self.publication.publish_checkpoint(
                checkpoint=CheckpointRecord(
                    checkpoint_id=checkpoint_id,
                    parent_ref=attempt.attempt_id,
                    creation_timestamp=attempt.start_timestamp,
                    state_snapshot_ref=GiteaStateControlPlaneExecutionService.snapshot_ref(
                        card_id=card_id,
                        from_state=from_state,
                        lease_observation=lease_observation,
                    ),
                    resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
                    invalidation_conditions=[
                        "lease_epoch_mismatch",
                        "gitea_card_state_changed",
                        "gitea_card_snapshot_missing",
                    ],
                    dependent_resource_ids=self._dependent_resource_ids(card_id=card_id),
                    dependent_effect_refs=[],
                    policy_digest=run.policy_digest,
                    integrity_verification_ref=self._integrity_ref(
                        card_id=card_id,
                        from_state=from_state,
                        lease_observation=lease_observation,
                    ),
                )
            )
        else:
            checkpoint = existing_checkpoint

        existing_acceptance = await self.publication.repository.get_checkpoint_acceptance(
            checkpoint_id=checkpoint.checkpoint_id
        )
        if existing_acceptance is not None:
            return checkpoint, existing_acceptance

        acceptance = await self.publication.accept_checkpoint(
            acceptance_id=self.acceptance_id_for(attempt_id=attempt.attempt_id),
            checkpoint=checkpoint,
            supervisor_authority_ref=f"gitea-state-supervisor:{run.run_id}",
            decision_timestamp=checkpoint.creation_timestamp,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
        )
        return checkpoint, acceptance

    @staticmethod
    def checkpoint_id_for(*, attempt_id: str) -> str:
        return f"gitea-state-checkpoint:{attempt_id}"

    @staticmethod
    def acceptance_id_for(*, attempt_id: str) -> str:
        return f"gitea-state-checkpoint-acceptance:{attempt_id}"

    @staticmethod
    def _dependent_resource_ids(*, card_id: str) -> list[str]:
        normalized_card_id = str(card_id).strip()
        namespace_scope = GiteaStateControlPlaneExecutionService.namespace_scope_for(card_id=normalized_card_id)
        return [f"gitea-card:{normalized_card_id}", f"issue:{normalized_card_id}", f"namespace:{namespace_scope}"]

    @staticmethod
    def _integrity_ref(
        *,
        card_id: str,
        from_state: str,
        lease_observation: Mapping[str, object],
    ) -> str:
        raw = json.dumps(
            {
                "card_id": str(card_id),
                "from_state": str(from_state),
                "lease_observation": dict(lease_observation),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        ).encode("ascii")
        return f"gitea-state-checkpoint-integrity:sha256:{hashlib.sha256(raw).hexdigest()}"


def build_gitea_state_control_plane_checkpoint_service(
    db_path: str | Path | None = None,
) -> GiteaStateControlPlaneCheckpointService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneCheckpointService(publication=publication)


__all__ = [
    "GiteaStateControlPlaneCheckpointError",
    "GiteaStateControlPlaneCheckpointService",
    "build_gitea_state_control_plane_checkpoint_service",
]
