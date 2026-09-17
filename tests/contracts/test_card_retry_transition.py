"""System retries requeue failed review turns without granting model status authority."""
from __future__ import annotations

import pytest

from orket.core.domain.workitem_transition import TransitionErrorCode, WorkItemTransitionService
from orket.schema import CardStatus

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("reason", ["retry_scheduled", "runtime_guard_retry_scheduled"])
# Layer: contract
def test_guard_review_system_retry_requeues_with_both_gate_hooks(reason):
    calls = []

    class Gates:
        def pre_transition(self, **kwargs):
            calls.append("pre")

        def post_transition(self, **kwargs):
            calls.append("post")

    service = WorkItemTransitionService(gate_boundary=Gates())
    result = service.request_transition(action="system_set_status", current_status=CardStatus.AWAITING_GUARD_REVIEW,
                                        payload={"status": "ready", "reason": reason}, roles=["system"])
    assert result.ok and result.new_status == "ready"
    assert result.metadata["system_retry_requeue"] is True and calls == ["pre", "post"]


@pytest.mark.parametrize("action,reason", [("set_status", "retry_scheduled"),
                                           ("system_set_status", "force_ready")])
# Layer: contract
def test_guard_review_requeue_does_not_admit_ordinary_or_unrelated_requests(action, reason):
    result = WorkItemTransitionService().request_transition(
        action=action, current_status=CardStatus.AWAITING_GUARD_REVIEW,
        payload={"status": "ready", "reason": reason}, roles=["integrity_guard"])
    assert not result.ok and result.error_code == TransitionErrorCode.POLICY_VIOLATION


@pytest.mark.parametrize("status", [CardStatus.GUARD_APPROVED, CardStatus.GUARD_REJECTED, CardStatus.DONE,
                                     CardStatus.CANCELED, CardStatus.ARCHIVED])
# Layer: contract
def test_retry_reason_cannot_reopen_terminal_card(status):
    result = WorkItemTransitionService().request_transition(
        action="system_set_status", current_status=status,
        payload={"status": "ready", "reason": "retry_scheduled"}, roles=["system"])
    assert not result.ok and result.error_code == TransitionErrorCode.POLICY_VIOLATION
