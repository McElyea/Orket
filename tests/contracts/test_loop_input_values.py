"""Loop defaults match observed installed .47 results; borrowed state is refused."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.application.services.decision_context_service import capture_backlog_inputs
from orket.application.services.decision_node_registry import DecisionNodeRegistry
from orket.application.services.loop_decision_service import (
    capture_seat_policy_input,
    recommend_exhaustion,
    recommend_no_candidate,
    validate_guard_review,
)
from orket.application.services.orchestrator_turn_context_policy import resolve_policy_list, resolve_policy_token
from orket.core.contracts.decision_inputs import GuardReviewInput, LoopPolicyInputs
from orket.core.domain.guard_review import GuardReviewPayload
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.builtins import DefaultOrchestrationLoopPolicyNode
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus, IssueConfig

pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def reference():
    return json.loads((Path(__file__).parents[1]/"fixtures/loop_policy_v047.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", range(36))
def test_seat_policy_defaults_preserve_published_outcomes(reference, case):
    row = reference["seats"][case]
    issue = IssueConfig(**row["issue"]) if row["issue"] else None
    inputs = capture_seat_policy_input(row["seat"], issue, CardStatus.IN_PROGRESS)
    node = DefaultOrchestrationLoopPolicyNode()
    for method, expected in row["outcomes"].items():
        assert getattr(node, method)(inputs) == expected


@pytest.mark.parametrize("status", list(CardStatus))
def test_loop_terminal_and_exhaustion_results_preserve_published_outcomes(reference, status):
    node = DefaultOrchestrationLoopPolicyNode()
    inputs = capture_backlog_inputs((IssueConfig(id="card", summary="Original", status=status),))
    expected = reference["statuses"][status.value]
    assert node.is_backlog_done(inputs) is expected["done"]
    assert node.no_candidate_outcome(inputs) == expected["outcome"]
    assert recommend_exhaustion(node, 20, 20, inputs) is expected["exhaustion"]
    assert recommend_exhaustion(node, 19, 20, inputs) is False


@pytest.mark.parametrize("case", range(5))
def test_guard_defaults_preserve_published_outcomes(reference, case):
    row = reference["guards"][case]
    inputs = GuardReviewInput.model_validate(row["input"])
    assert DefaultOrchestrationLoopPolicyNode().validate_guard_rejection_payload(inputs) == row["outcome"]
    assert validate_guard_review(SimpleNamespace(), GuardReviewPayload(**row["input"])) == row["outcome"]


@pytest.mark.parametrize("case", range(6))
def test_role_order_preserves_published_outcomes(reference, case):
    row = reference["roles"][case]
    assert DefaultOrchestrationLoopPolicyNode().role_order_for_turn(tuple(row["roles"]), row["review"]) == row["outcome"]


def test_default_registry_loop_configuration_and_status_contract():
    node = DecisionNodeRegistry().resolve_orchestration_loop()
    assert isinstance(node, DefaultOrchestrationLoopPolicyNode)
    assert node.context_window(LoopPolicyInputs()) == 10
    assert node.is_review_turn(CardStatus.CODE_REVIEW) is True
    assert node.is_review_turn(CardStatus.READY) is False
    assert node.turn_status_for_issue(True) == CardStatus.CODE_REVIEW
    assert node.turn_status_for_issue(False) == CardStatus.IN_PROGRESS
    assert node.missing_seat_status() == CardStatus.CANCELED
    assert node.is_backlog_done(()) is True


def test_seat_and_backlog_inputs_are_detached_nested_values():
    issue = IssueRecord(id="card", summary="Original", seat="coder", depends_on=["prior"],
        params={"artifact_contract": {"kind": "artifact", "required_write_paths": ["out.txt"]}})
    inputs = capture_seat_policy_input("coder", issue, CardStatus.IN_PROGRESS)
    issue.summary = "Changed externally"
    issue.params["artifact_contract"]["required_write_paths"].clear()
    assert inputs.issue.summary == "Original" and inputs.required_write_paths == ("out.txt",)
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.issue.summary = "Changed"
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.issue.depends_on += ("replacement",)
    assert not hasattr(inputs.issue, "params")


def test_strategy_type_error_is_observed_once_without_signature_retry():
    calls = []
    def failed(inputs):
        calls.append(inputs)
        raise TypeError("Entered strategy failed")
    node = SimpleNamespace(required_action_tools_for_seat=failed, gate_mode_for_seat=failed)
    inputs = capture_seat_policy_input("coder", None, CardStatus.IN_PROGRESS)
    for resolver, attribute, extra in [(resolve_policy_list, "required_action_tools_for_seat", {}),
                                       (resolve_policy_token, "gate_mode_for_seat", {"default": "auto"})]:
        with pytest.raises(TypeError, match="Entered strategy failed"):
            resolver(loop_policy_node=node, attribute=attribute, inputs=inputs, **extra)
    assert calls == [inputs, inputs]


@pytest.mark.parametrize("proposal", [None, "write_file", [None], [1], {"write_file": True}])
def test_policy_names_refuse_non_contract_values(proposal):
    node = SimpleNamespace(required_action_tools_for_seat=lambda inputs: proposal)
    with pytest.raises(ExecutionFailed, match="E_LOOP_POLICY_INVALID_NAMES"):
        resolve_policy_list(loop_policy_node=node, attribute="required_action_tools_for_seat",
                            inputs=capture_seat_policy_input("coder", None, CardStatus.IN_PROGRESS))


def test_guard_inputs_and_recommendations_cannot_rewrite_retained_payload():
    payload = GuardReviewPayload(rationale="Original", violations=["Finding"], remediation_actions=["Fix"])
    def mutate(inputs):
        inputs.remediation_actions += ("Changed",)
    with pytest.raises(ValidationError, match="frozen_instance"):
        validate_guard_review(SimpleNamespace(validate_guard_rejection_payload=mutate), payload)
    assert payload.remediation_actions == ["Fix"]
    result = validate_guard_review(SimpleNamespace(), payload)
    with pytest.raises(TypeError):
        result["valid"] = False


@pytest.mark.parametrize("proposal", ["false", 0, None, [], {}])
def test_loop_recommendations_refuse_truthiness_coercion(proposal):
    with pytest.raises(ValidationError):
        recommend_no_candidate(SimpleNamespace(no_candidate_outcome=lambda inputs: {"is_done": proposal}), ())
    with pytest.raises(ExecutionFailed, match="E_LOOP_POLICY_INVALID_BOOLEAN"):
        recommend_exhaustion(SimpleNamespace(should_raise_exhaustion=lambda *args: proposal), 20, 20, ())
