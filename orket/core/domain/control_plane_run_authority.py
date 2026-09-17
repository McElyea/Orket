"""Immutable admission fields shared by control-plane run writers and reentry."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import RunRecord


# New contract fields remain immutable unless explicitly admitted as state here.
RUN_STATE_FIELDS = frozenset({"lifecycle_state", "current_attempt_id", "final_truth_record_id", "state_revision"})


def same_run_admission(existing: RunRecord, incoming: RunRecord) -> bool:
    return existing.model_dump(exclude=RUN_STATE_FIELDS) == incoming.model_dump(exclude=RUN_STATE_FIELDS)
