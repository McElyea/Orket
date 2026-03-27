from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import ResolvedConfigurationSnapshot, ResolvedPolicySnapshot, RunRecord


def snapshot_digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


async def publish_run_snapshots(
    *,
    publication: ControlPlanePublicationService | None,
    run: RunRecord,
    policy_payload: Mapping[str, Any],
    policy_source_refs: Sequence[str],
    configuration_payload: Mapping[str, Any],
    configuration_source_refs: Sequence[str],
) -> tuple[ResolvedPolicySnapshot, ResolvedConfigurationSnapshot]:
    policy_snapshot = ResolvedPolicySnapshot(
        snapshot_id=run.policy_snapshot_id,
        snapshot_digest=run.policy_digest,
        created_at=run.creation_timestamp,
        source_refs=list(policy_source_refs),
        policy_payload=dict(policy_payload),
    )
    configuration_snapshot = ResolvedConfigurationSnapshot(
        snapshot_id=run.configuration_snapshot_id,
        snapshot_digest=run.configuration_digest,
        created_at=run.creation_timestamp,
        source_refs=list(configuration_source_refs),
        configuration_payload=dict(configuration_payload),
    )
    if publication is not None:
        await publication.repository.save_resolved_policy_snapshot(snapshot=policy_snapshot)
        await publication.repository.save_resolved_configuration_snapshot(snapshot=configuration_snapshot)
    return policy_snapshot, configuration_snapshot

__all__ = ["publish_run_snapshots", "snapshot_digest"]
