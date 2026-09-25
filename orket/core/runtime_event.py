"""Pure runtime-event projection shared by logging publication."""
from __future__ import annotations

from typing import Any

from orket.core.contracts.invocation_timing import optional_duration_ms

RUNTIME_EVENT_SCHEMA_VERSION = "v2"
RUNTIME_EVENT_ARTIFACT_EVENTS = {
    "determinism_violation", "packet1_emission_failure", "session_start", "session_end", "turn_start",
    "turn_complete", "turn_failed", "runtime_verifier_completed", "guard_retry_scheduled", "guard_terminal_failure",
    "sdk_capability_call_start", "sdk_capability_call_blocked", "sdk_capability_call_result", "sdk_capability_call_exception",
}


def _build_runtime_event(event: str, data: dict[str, Any], role: str) -> dict[str, Any]:
    payload = dict(data or {})
    return {
        "schema_version": RUNTIME_EVENT_SCHEMA_VERSION,
        "event": str(event or "").strip(),
        "role": str(role or payload.get("role") or "system"),
        "session_id": str(payload.get("session_id") or ""),
        "run_id": str(payload.get("run_id") or ""),
        "issue_id": str(payload.get("issue_id") or ""),
        "turn_index": int(payload.get("turn_index") or 0),
        "turn_trace_id": str(payload.get("turn_trace_id") or ""),
        "extension_id": str(payload.get("extension_id") or ""),
        "workload_id": str(payload.get("workload_id") or ""),
        "capability_id": str(payload.get("capability_id") or ""),
        "capability_family": str(payload.get("capability_family") or ""),
        "authorization_basis": str(payload.get("authorization_basis") or ""),
        "declared": payload.get("declared"),
        "admitted": payload.get("admitted"),
        "side_effect_observed": payload.get("side_effect_observed"),
        "denial_class": str(payload.get("denial_class") or ""),
        "selected_model": str(payload.get("selected_model") or ""),
        "prompt_id": str(payload.get("prompt_id") or ""),
        "prompt_version": str(payload.get("prompt_version") or ""),
        "prompt_checksum": str(payload.get("prompt_checksum") or ""),
        "resolver_policy": str(payload.get("resolver_policy") or ""),
        "selection_policy": str(payload.get("selection_policy") or ""),
        "execution_profile": str(payload.get("execution_profile") or ""),
        "builder_seat_choice": str(payload.get("builder_seat_choice") or ""),
        "reviewer_seat_choice": str(payload.get("reviewer_seat_choice") or ""),
        "seat_coercion": payload.get("seat_coercion"),
        "artifact_contract": payload.get("artifact_contract"),
        "odr_active": bool(payload.get("odr_active", False)),
        "odr_stop_reason": str(payload.get("odr_stop_reason") or ""),
        "odr_valid": payload.get("odr_valid"),
        "odr_pending_decisions": payload.get("odr_pending_decisions"),
        "stop_reason": str(payload.get("stop_reason") or ""),
        "guard_contract": payload.get("guard_contract"),
        "guard_decision": payload.get("guard_decision"),
        "terminal_reason": (
            (payload.get("guard_decision") or {}).get("terminal_reason")
            if isinstance(payload.get("guard_decision"), dict)
            else None
        ),
        "stage": str(payload.get("stage") or ""),
        "tool": str(payload.get("tool") or ""),
        "error_type": str(payload.get("error_type") or ""),
        "error": str(payload.get("error") or ""), "error_code": str(payload.get("error_code") or ""),
        "determinism_class": str(payload.get("determinism_class") or ""),
        "capability_profile": str(payload.get("capability_profile") or ""),
        "tool_contract_version": str(payload.get("tool_contract_version") or ""),
        "side_effect_signal_keys": list(payload.get("side_effect_signal_keys") or []),
        "packet1_conformance": payload.get("packet1_conformance"),
        "duration_ms": optional_duration_ms(payload.get("duration_ms")),
        **({"timing": payload["timing"]} if "timing" in payload else {}),
        "tokens": payload.get("tokens"),
    }
