"""Shared read-only checkpoint snapshot semantics."""
from __future__ import annotations

from typing import Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.core.domain import CheckpointResumabilityClass


def validate_resume_snapshot_semantics(
    *,
    snapshot_payload: dict[str, Any],
    attempt_id: str,
    resumability_class: CheckpointResumabilityClass,
) -> None:
    control_plane = snapshot_payload.get("control_plane")
    if not isinstance(control_plane, dict):
        raise TurnToolControlPlaneError(
            f"resumed governed attempt {attempt_id} has malformed checkpoint snapshot control-plane metadata"
        )
    resumability = str(control_plane.get("resumability_class") or "").strip()
    recovery_mode = str(control_plane.get("recovery_mode") or "").strip()
    expected_recovery_mode = (
        "pre_effect_same_attempt_only"
        if resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
        else "pre_effect_new_attempt_only"
    )
    if resumability != resumability_class.value:
        raise TurnToolControlPlaneError(
            f"resumed governed attempt {attempt_id} requires {resumability_class.value} snapshot semantics"
        )
    if recovery_mode != expected_recovery_mode:
        raise TurnToolControlPlaneError(
            f"resumed governed attempt {attempt_id} requires {expected_recovery_mode} checkpoint recovery semantics"
        )
