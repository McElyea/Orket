from __future__ import annotations

from collections.abc import Iterable

UNKNOWN_INPUT_POLICY_SCHEMA_VERSION = "1.0"

_EXPECTED_UNKNOWN_INPUT_SURFACES = {
    "provider_runtime_target.requested_provider",
    "runtime_status_vocabulary.token",
    "state_transition_registry.domain",
    "state_transition_registry.state",
    "streaming_semantics.event",
}


def unknown_input_policy_snapshot() -> dict[str, object]:
    return {
        "schema_version": UNKNOWN_INPUT_POLICY_SCHEMA_VERSION,
        "surfaces": [
            {
                "surface": "provider_runtime_target.requested_provider",
                "on_unknown": "fail_closed",
                "error_code": "E_UNKNOWN_PROVIDER_INPUT",
            },
            {
                "surface": "runtime_status_vocabulary.token",
                "on_unknown": "fail_closed",
                "error_code": "E_RUNTIME_STATUS_UNKNOWN",
            },
            {
                "surface": "state_transition_registry.domain",
                "on_unknown": "fail_closed",
                "error_code": "E_STATE_DOMAIN_UNKNOWN",
            },
            {
                "surface": "state_transition_registry.state",
                "on_unknown": "fail_closed",
                "error_code": "E_STATE_TOKEN_UNKNOWN",
            },
            {
                "surface": "streaming_semantics.event",
                "on_unknown": "fail_closed",
                "error_code": "E_STREAM_EVENT_UNKNOWN",
            },
        ],
    }


def validate_unknown_input_policy(
    payload: dict[str, object] | None = None,
) -> tuple[str, ...]:
    policy = dict(payload or unknown_input_policy_snapshot())
    surfaces_payload = policy.get("surfaces")
    rows = surfaces_payload if isinstance(surfaces_payload, list) else []
    if not rows:
        raise ValueError("E_UNKNOWN_INPUT_POLICY_EMPTY")

    surfaces: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_UNKNOWN_INPUT_POLICY_ROW_SCHEMA")
        surface = str(row.get("surface") or "").strip()
        on_unknown = str(row.get("on_unknown") or "").strip().lower()
        error_code = str(row.get("error_code") or "").strip()
        if not surface or not error_code:
            raise ValueError("E_UNKNOWN_INPUT_POLICY_ROW_SCHEMA")
        if on_unknown != "fail_closed":
            raise ValueError(f"E_UNKNOWN_INPUT_POLICY_ON_UNKNOWN_INVALID:{surface}")
        surfaces.append(surface)

    if len(set(surfaces)) != len(surfaces):
        raise ValueError("E_UNKNOWN_INPUT_POLICY_DUPLICATE_SURFACE")
    if set(surfaces) != _EXPECTED_UNKNOWN_INPUT_SURFACES:
        raise ValueError("E_UNKNOWN_INPUT_POLICY_SURFACE_SET_MISMATCH")
    return tuple(sorted(surfaces))


def validate_allowed_token(
    *,
    token: str,
    allowed: Iterable[str],
    error_code_prefix: str,
) -> str:
    normalized = str(token or "").strip().lower()
    allowed_tokens = {str(item or "").strip().lower() for item in allowed if str(item or "").strip()}
    if normalized not in allowed_tokens:
        raise ValueError(f"{str(error_code_prefix or '').strip()}:{normalized or '<empty>'}")
    return normalized
