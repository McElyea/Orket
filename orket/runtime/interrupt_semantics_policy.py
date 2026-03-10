from __future__ import annotations

from typing import Any


INTERRUPT_SEMANTICS_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_SURFACES = {
    "run_execution",
    "tool_invocation",
    "streaming_output",
    "voice_playback",
    "ui_render",
}
_ALLOWED_MODES = {"cooperative", "forced", "deferred"}
_ALLOWED_OUTCOME_STATES = {"cancelled", "degraded", "failed"}

_POLICY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "surface": "run_execution",
        "interrupt_modes": ["cooperative", "forced"],
        "required_effects": [
            "stop_new_work",
            "emit_runtime_warning",
            "persist_terminal_state",
        ],
        "outcome_state": "cancelled",
        "idempotency_required": True,
    },
    {
        "surface": "tool_invocation",
        "interrupt_modes": ["cooperative", "forced"],
        "required_effects": [
            "cancel_inflight_tool",
            "emit_tool_cancel_event",
            "preserve_partial_artifacts",
        ],
        "outcome_state": "degraded",
        "idempotency_required": True,
    },
    {
        "surface": "streaming_output",
        "interrupt_modes": ["cooperative"],
        "required_effects": [
            "emit_stream_terminal_event",
            "flush_stream_buffer",
            "persist_terminal_state",
        ],
        "outcome_state": "cancelled",
        "idempotency_required": True,
    },
    {
        "surface": "voice_playback",
        "interrupt_modes": ["cooperative", "forced"],
        "required_effects": [
            "stop_audio_output",
            "mark_voice_state_interrupted",
            "persist_terminal_state",
        ],
        "outcome_state": "cancelled",
        "idempotency_required": True,
    },
    {
        "surface": "ui_render",
        "interrupt_modes": ["deferred"],
        "required_effects": [
            "suppress_stale_render",
            "emit_ui_interrupt_notice",
            "preserve_user_context",
        ],
        "outcome_state": "degraded",
        "idempotency_required": True,
    },
)


def interrupt_semantics_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": INTERRUPT_SEMANTICS_POLICY_SCHEMA_VERSION,
        "rows": [dict(row) for row in _POLICY_ROWS],
    }


def validate_interrupt_semantics_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or interrupt_semantics_policy_snapshot())
    rows = list(policy.get("rows") or [])
    if not rows:
        raise ValueError("E_INTERRUPT_SEMANTICS_POLICY_EMPTY")

    observed_surfaces: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_INTERRUPT_SEMANTICS_POLICY_ROW_SCHEMA")
        surface = str(row.get("surface") or "").strip().lower()
        if not surface:
            raise ValueError("E_INTERRUPT_SEMANTICS_POLICY_SURFACE_REQUIRED")

        modes = [str(token or "").strip().lower() for token in row.get("interrupt_modes", [])]
        if not modes:
            raise ValueError(f"E_INTERRUPT_SEMANTICS_POLICY_MODES_REQUIRED:{surface}")
        if any(mode not in _ALLOWED_MODES for mode in modes):
            raise ValueError(f"E_INTERRUPT_SEMANTICS_POLICY_MODE_INVALID:{surface}")

        effects = [str(token or "").strip() for token in row.get("required_effects", [])]
        if not effects or any(not token for token in effects):
            raise ValueError(f"E_INTERRUPT_SEMANTICS_POLICY_EFFECTS_REQUIRED:{surface}")

        outcome_state = str(row.get("outcome_state") or "").strip().lower()
        if outcome_state not in _ALLOWED_OUTCOME_STATES:
            raise ValueError(f"E_INTERRUPT_SEMANTICS_POLICY_OUTCOME_INVALID:{surface}")

        idempotency_required = row.get("idempotency_required")
        if not isinstance(idempotency_required, bool):
            raise ValueError(f"E_INTERRUPT_SEMANTICS_POLICY_IDEMPOTENCY_INVALID:{surface}")

        observed_surfaces.append(surface)

    if len(set(observed_surfaces)) != len(observed_surfaces):
        raise ValueError("E_INTERRUPT_SEMANTICS_POLICY_DUPLICATE_SURFACE")
    if set(observed_surfaces) != _EXPECTED_SURFACES:
        raise ValueError("E_INTERRUPT_SEMANTICS_POLICY_SURFACE_SET_MISMATCH")
    return tuple(sorted(observed_surfaces))
