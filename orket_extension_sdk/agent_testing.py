from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, cast

from .agent_models import (
    AgentMemoryQueryRequest,
    AgentMemoryQueryResult,
    AgentModelCallRequest,
    AgentModelCallResult,
)
from .agent_types import AgentCancellation
from .controller import canonical_digest_sha256, canonical_json


class ScriptedAgentModelCapability:
    """Deterministic test capability that returns prevalidated host results."""

    def __init__(self, results: Iterable[AgentModelCallResult]) -> None:
        self._results = deque(results)
        self.requests: list[AgentModelCallRequest] = []

    async def call(self, request: AgentModelCallRequest) -> AgentModelCallResult:
        if not self._results:
            raise ValueError("E_SDK_TEST_MODEL_RESULT_EXHAUSTED")
        result = self._results.popleft()
        if (
            result.identity != request.identity
            or result.call_id != request.call_id
            or result.role != request.role
        ):
            raise ValueError("E_SDK_TEST_MODEL_RESULT_MISMATCH")
        self.requests.append(request)
        return result


class ScriptedAgentMemoryCapability:
    """Deterministic test capability that returns prevalidated memory results."""

    def __init__(self, results: Iterable[AgentMemoryQueryResult]) -> None:
        self._results = deque(results)
        self.requests: list[AgentMemoryQueryRequest] = []

    async def query(self, request: AgentMemoryQueryRequest) -> AgentMemoryQueryResult:
        if not self._results:
            raise ValueError("E_SDK_TEST_MEMORY_RESULT_EXHAUSTED")
        result = self._results.popleft()
        if result.identity != request.identity or result.call_id != request.call_id:
            raise ValueError("E_SDK_TEST_MEMORY_RESULT_MISMATCH")
        self.requests.append(request)
        return result


def host_cancellation(*, epoch: int, reason: str) -> AgentCancellation:
    return AgentCancellation(requested=True, cancellation_epoch=epoch, reason=reason)


def canonical_agent_digest(payload: Any) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(payload))


def assert_canonical_agent_payload_equal(actual: Any, expected: Any) -> None:
    actual_json = canonical_json(actual)
    expected_json = canonical_json(expected)
    if actual_json != expected_json:
        raise AssertionError(f"canonical agent payload mismatch:\nactual={actual_json}\nexpected={expected_json}")


def ticket_report_fixture() -> dict[str, Any]:
    """Return the shared two-iteration acceptance fixture as a fresh value."""
    return deepcopy(
        {
            "objective": {"task": "Produce ticket counts by status from both batches."},
            "acceptance": {
                "required_fields": ["counts", "source_refs"],
                "required_source_refs": ["artifact:ticket-batch-a", "artifact:ticket-batch-b"],
            },
            "batches": {
                "artifact:ticket-batch-a": [
                    {"ticket_id": "A-1", "status": "open"},
                    {"ticket_id": "A-2", "status": "closed"},
                    {"ticket_id": "A-3", "status": "open"},
                ],
                "artifact:ticket-batch-b": [
                    {"ticket_id": "B-1", "status": "blocked"},
                    {"ticket_id": "B-2", "status": "closed"},
                ],
            },
            "expected_report": {
                "counts": {"blocked": 1, "closed": 2, "open": 2},
                "source_refs": ["artifact:ticket-batch-a", "artifact:ticket-batch-b"],
            },
        }
    )
