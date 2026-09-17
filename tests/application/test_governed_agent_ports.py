from __future__ import annotations

import pytest

from orket.core.contracts.governed_agent_ports import (
    GovernedAgentInvocationBinding,
    GovernedAgentInvocationOutcome,
)

pytestmark = pytest.mark.contract


def _binding() -> GovernedAgentInvocationBinding:
    return GovernedAgentInvocationBinding(
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        iteration_ordinal=1,
        invocation_id="invocation-1",
        fencing_generation=1,
        cancellation_epoch=0,
        deadline_utc="2026-09-06T18:00:00Z",
        extension_digest="sha256:" + "a" * 64,
        policy_digest="sha256:" + "b" * 64,
        request_digest="sha256:" + "c" * 64,
    )


def test_invocation_binding_requires_parent_and_fencing_identity() -> None:
    binding = _binding()

    assert binding.run_id == "run-1"
    assert binding.fencing_generation == 1


def test_returned_outcome_requires_digest_addressed_result() -> None:
    with pytest.raises(ValueError, match="E_AGENT_INVOCATION_RESULT_REQUIRED"):
        GovernedAgentInvocationOutcome(
            status="returned",
            binding=_binding(),
            result_payload=None,
            result_digest=None,
            normalized_reason=None,
            child_confirmed_stopped=True,
        )


def test_failed_outcome_requires_normalized_reason() -> None:
    with pytest.raises(ValueError, match="E_AGENT_INVOCATION_FAILURE_REASON_REQUIRED"):
        GovernedAgentInvocationOutcome(
            status="protocol_failed",
            binding=_binding(),
            result_payload=None,
            result_digest=None,
            normalized_reason=None,
            child_confirmed_stopped=True,
        )
