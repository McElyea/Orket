from __future__ import annotations

import pytest

from orket.runtime.timeout_streaming_contracts import (
    streaming_semantics_snapshot,
    timeout_semantics_snapshot,
    validate_streaming_event_trace,
)


# Layer: unit
def test_timeout_semantics_snapshot_contains_expected_surfaces() -> None:
    payload = timeout_semantics_snapshot()
    assert payload["schema_version"] == "1.0"
    surfaces = [row["surface"] for row in payload["timeout_surfaces"]]
    assert surfaces == [
        "local_model_completion_timeout",
        "model_stream_provider_timeout",
        "model_stream_turn_timeout",
        "provider_runtime_inventory_timeout",
    ]


# Layer: contract
def test_streaming_semantics_snapshot_declares_terminal_events() -> None:
    payload = streaming_semantics_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["terminal_events"] == ["error", "stopped"]


# Layer: contract
def test_validate_streaming_event_trace_accepts_happy_path() -> None:
    trace = validate_streaming_event_trace(
        ["selected", "loading", "ready", "token_delta", "token_delta", "stopped"]
    )
    assert trace[-1] == "stopped"


# Layer: contract
def test_validate_streaming_event_trace_rejects_missing_terminal_event() -> None:
    with pytest.raises(ValueError, match="E_STREAM_EVENT_TERMINAL_REQUIRED"):
        _ = validate_streaming_event_trace(["selected", "loading", "ready", "token_delta"])


# Layer: contract
def test_validate_streaming_event_trace_rejects_token_delta_before_ready() -> None:
    with pytest.raises(ValueError, match="E_STREAM_EVENT_ORDER:loading->token_delta"):
        _ = validate_streaming_event_trace(["selected", "loading", "token_delta", "error"])
