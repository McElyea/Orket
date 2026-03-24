from __future__ import annotations

from collections.abc import Sequence

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.turn_tool_control_plane_support import utc_now
from orket.core.contracts import CheckpointAcceptanceRecord, CheckpointRecord, RunRecord
from orket.core.domain import (
    DivergenceClass,
    ResidualUncertaintyClassification,
    SafeContinuationClass,
)


async def publish_resume_reconciliation(
    *,
    publication: ControlPlanePublicationService,
    run: RunRecord,
    checkpoint: CheckpointRecord,
    acceptance: CheckpointAcceptanceRecord,
    step_refs: Sequence[str],
    effect_refs: Sequence[str],
) -> tuple[object, list[str]]:
    observed_refs = list(effect_refs) if effect_refs else list(step_refs)
    intended_refs = [
        checkpoint.checkpoint_id,
        acceptance.acceptance_id,
        checkpoint.state_snapshot_ref,
    ]
    if effect_refs:
        divergence = DivergenceClass.UNEXPECTED_EFFECT_OBSERVED
    else:
        divergence = DivergenceClass.INSUFFICIENT_OBSERVATION
    record = await publication.publish_reconciliation(
        reconciliation_id=f"turn-tool-reconciliation:{run.run_id}:{run.current_attempt_id or 'no-attempt'}",
        target_ref=run.run_id,
        comparison_scope="turn_resume_boundary",
        observed_refs=observed_refs,
        intended_refs=intended_refs,
        divergence_class=divergence,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp=utc_now(),
        safe_continuation_class=SafeContinuationClass.UNSAFE_TO_CONTINUE,
    )
    return record, [*intended_refs, *observed_refs]


__all__ = ["publish_resume_reconciliation"]
