from __future__ import annotations

from typing import Any

IDEMPOTENCY_DISCIPLINE_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_SURFACES = {
    "status_update",
    "source_attribution_receipt",
    "run_finalize",
    "artifact_write",
    "task_execution",
    "phase_transition",
    "tool_result_persist",
}
_ALLOWED_CONFLICT_ACTIONS = {"reuse", "reject", "warn"}

_POLICY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "surface": "run_finalize",
        "key_fields": ["run_id", "phase", "attempt"],
        "conflict_action": "reject",
        "replay_allowed": False,
    },
    {
        "surface": "artifact_write",
        "key_fields": ["run_id", "artifact_path", "artifact_hash"],
        "conflict_action": "reuse",
        "replay_allowed": True,
    },
    {
        "surface": "status_update",
        "key_fields": ["run_id", "issue_id", "status", "operation_id"],
        "conflict_action": "reuse",
        "replay_allowed": True,
    },
    {
        "surface": "source_attribution_receipt",
        "key_fields": ["run_id", "artifact_path", "operation_id", "source_hash"],
        "conflict_action": "reuse",
        "replay_allowed": True,
    },
    {
        "surface": "task_execution",
        "key_fields": ["run_id", "task_id", "task_input_hash"],
        "conflict_action": "reuse",
        "replay_allowed": True,
    },
    {
        "surface": "phase_transition",
        "key_fields": ["run_id", "from_phase", "to_phase", "sequence"],
        "conflict_action": "reject",
        "replay_allowed": False,
    },
    {
        "surface": "tool_result_persist",
        "key_fields": ["run_id", "tool_name", "call_sequence_number", "result_hash"],
        "conflict_action": "warn",
        "replay_allowed": True,
    },
)


def idempotency_discipline_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": IDEMPOTENCY_DISCIPLINE_POLICY_SCHEMA_VERSION,
        "rows": [dict(row) for row in _POLICY_ROWS],
    }


def validate_idempotency_discipline_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(payload or idempotency_discipline_policy_snapshot())
    rows = list(policy.get("rows") or [])
    if not rows:
        raise ValueError("E_IDEMPOTENCY_DISCIPLINE_POLICY_EMPTY")

    observed_surfaces: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_IDEMPOTENCY_DISCIPLINE_POLICY_ROW_SCHEMA")
        surface = str(row.get("surface") or "").strip().lower()
        if not surface:
            raise ValueError("E_IDEMPOTENCY_DISCIPLINE_POLICY_SURFACE_REQUIRED")

        key_fields = [str(token or "").strip() for token in row.get("key_fields", [])]
        if not key_fields or any(not token for token in key_fields):
            raise ValueError(f"E_IDEMPOTENCY_DISCIPLINE_POLICY_KEYS_REQUIRED:{surface}")

        conflict_action = str(row.get("conflict_action") or "").strip().lower()
        if conflict_action not in _ALLOWED_CONFLICT_ACTIONS:
            raise ValueError(f"E_IDEMPOTENCY_DISCIPLINE_POLICY_CONFLICT_ACTION_INVALID:{surface}")

        replay_allowed = row.get("replay_allowed")
        if not isinstance(replay_allowed, bool):
            raise ValueError(f"E_IDEMPOTENCY_DISCIPLINE_POLICY_REPLAY_ALLOWED_INVALID:{surface}")

        observed_surfaces.append(surface)

    if len(set(observed_surfaces)) != len(observed_surfaces):
        raise ValueError("E_IDEMPOTENCY_DISCIPLINE_POLICY_DUPLICATE_SURFACE")
    if set(observed_surfaces) != _EXPECTED_SURFACES:
        raise ValueError("E_IDEMPOTENCY_DISCIPLINE_POLICY_SURFACE_SET_MISMATCH")
    return tuple(sorted(observed_surfaces))
