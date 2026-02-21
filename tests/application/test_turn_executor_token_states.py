from __future__ import annotations

from orket.application.workflows.turn_executor import TurnExecutor
from orket.domain.execution import ExecutionTurn


def _turn(raw: dict) -> ExecutionTurn:
    return ExecutionTurn(
        issue_id="I-1",
        role="coder",
        content="",
        thought="",
        tool_calls=[],
        tokens_used=42,
        raw=raw,
    )


def test_runtime_tokens_payload_state_ok() -> None:
    payload = TurnExecutor._runtime_tokens_payload(
        _turn(
            {
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "timings": {"prompt_ms": 100.0, "predicted_ms": 250.0},
            }
        )
    )
    assert payload["status"] == "OK"
    assert payload["prompt_tokens"] == 10
    assert payload["output_tokens"] == 5
    assert payload["total_tokens"] == 15
    assert payload["prompt_ms"] == 100.0
    assert payload["predicted_ms"] == 250.0


def test_runtime_tokens_payload_state_token_count_unavailable() -> None:
    payload = TurnExecutor._runtime_tokens_payload(
        _turn(
            {
                "usage": {"prompt_tokens": None, "completion_tokens": None},
                "timings": {"prompt_ms": 100.0, "predicted_ms": 250.0},
            }
        )
    )
    assert payload["status"] == "TOKEN_COUNT_UNAVAILABLE"
    assert payload["prompt_tokens"] is None
    assert payload["output_tokens"] is None
    assert payload["total_tokens"] == 42
    assert payload["prompt_ms"] == 100.0
    assert payload["predicted_ms"] == 250.0


def test_runtime_tokens_payload_state_timing_unavailable() -> None:
    payload = TurnExecutor._runtime_tokens_payload(
        _turn(
            {
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                "timings": {"prompt_ms": None, "predicted_ms": None},
            }
        )
    )
    assert payload["status"] == "TIMING_UNAVAILABLE"
    assert payload["prompt_tokens"] == 10
    assert payload["output_tokens"] == 5
    assert payload["total_tokens"] == 15
    assert payload["prompt_ms"] is None
    assert payload["predicted_ms"] is None


def test_runtime_tokens_payload_state_token_and_timing_unavailable() -> None:
    payload = TurnExecutor._runtime_tokens_payload(_turn({}))
    assert payload["status"] == "TOKEN_AND_TIMING_UNAVAILABLE"
    assert payload["prompt_tokens"] is None
    assert payload["output_tokens"] is None
    assert payload["total_tokens"] == 42
    assert payload["prompt_ms"] is None
    assert payload["predicted_ms"] is None
