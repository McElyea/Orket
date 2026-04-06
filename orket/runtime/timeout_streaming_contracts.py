from __future__ import annotations

from collections.abc import Iterable

TIMEOUT_SEMANTICS_SCHEMA_VERSION = "1.0"
STREAMING_SEMANTICS_SCHEMA_VERSION = "1.0"

_STREAMING_EVENT_ORDER = ("selected", "loading", "ready", "token_delta", "stopped", "error")
_TERMINAL_EVENTS = {"stopped", "error"}


def timeout_semantics_snapshot() -> dict[str, object]:
    return {
        "schema_version": TIMEOUT_SEMANTICS_SCHEMA_VERSION,
        "timeout_surfaces": [
            {
                "surface": "local_model_completion_timeout",
                "default_seconds": 300,
                "env_overrides": [],
                "failure_behavior": "retry_then_fail",
                "runtime_path": "orket/adapters/llm/local_model_provider.py",
            },
            {
                "surface": "model_stream_provider_timeout",
                "default_seconds": 20,
                "env_overrides": ["ORKET_MODEL_STREAM_REAL_TIMEOUT_S"],
                "failure_behavior": "provider_error",
                "runtime_path": "orket/workloads/model_stream_v1.py",
            },
            {
                "surface": "model_stream_turn_timeout",
                "default_seconds": 12,
                "env_overrides": ["ORKET_MODEL_STREAM_TURN_TIMEOUT_S"],
                "failure_behavior": "fail_closed",
                "runtime_path": "orket/workloads/model_stream_v1.py",
            },
            {
                "surface": "provider_runtime_inventory_timeout",
                "default_seconds": 20,
                "env_overrides": [
                    "ORKET_PROVIDER_RUNTIME_TIMEOUT_SEC",
                    "ORKET_MODEL_STREAM_REAL_TIMEOUT_S",
                ],
                "failure_behavior": "blocked",
                "runtime_path": "orket/runtime/provider_runtime_target.py",
            },
        ],
    }


def streaming_semantics_snapshot() -> dict[str, object]:
    return {
        "schema_version": STREAMING_SEMANTICS_SCHEMA_VERSION,
        "event_trace_order": list(_STREAMING_EVENT_ORDER),
        "terminal_events": sorted(_TERMINAL_EVENTS),
        "rules": [
            "stream traces must start with selected",
            "loading must occur before ready",
            "token_delta events may only occur after ready",
            "terminal event must be stopped or error",
            "no events are allowed after terminal",
        ],
    }


def validate_streaming_event_trace(events: Iterable[str]) -> tuple[str, ...]:
    trace = tuple(str(event or "").strip().lower() for event in events if str(event or "").strip())
    if not trace:
        raise ValueError("E_STREAM_EVENT_TRACE_REQUIRED")
    if trace[0] != "selected":
        raise ValueError(f"E_STREAM_EVENT_FIRST:{trace[0]}")
    seen_ready = False
    terminal_seen = False
    previous = ""
    for event in trace:
        if event not in _STREAMING_EVENT_ORDER:
            raise ValueError(f"E_STREAM_EVENT_UNKNOWN:{event}")
        if terminal_seen:
            raise ValueError(f"E_STREAM_EVENT_AFTER_TERMINAL:{event}")
        if event == "loading" and previous not in {"selected", "loading"}:
            raise ValueError(f"E_STREAM_EVENT_ORDER:{previous}->loading")
        if event == "ready" and previous not in {"loading", "ready"}:
            raise ValueError(f"E_STREAM_EVENT_ORDER:{previous}->ready")
        if event == "token_delta" and not seen_ready:
            raise ValueError(f"E_STREAM_EVENT_ORDER:{previous}->token_delta")
        if event in _TERMINAL_EVENTS and not seen_ready:
            raise ValueError(f"E_STREAM_EVENT_ORDER:{previous}->{event}")
        if event == "ready":
            seen_ready = True
        if event in _TERMINAL_EVENTS:
            terminal_seen = True
        previous = event
    if trace[-1] not in _TERMINAL_EVENTS:
        raise ValueError("E_STREAM_EVENT_TERMINAL_REQUIRED")
    return trace
