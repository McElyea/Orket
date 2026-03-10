from __future__ import annotations

from typing import Iterable


UNKNOWN_INPUT_POLICY_SCHEMA_VERSION = "1.0"


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
