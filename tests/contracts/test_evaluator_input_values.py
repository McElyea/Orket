"""Contract proof for evaluator snapshots and read-only primitive recommendations."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.application.services.decision_context_service import (
    admit_failure_recommendation,
    admit_success_actions,
    admit_success_recommendation,
    capture_failure_evaluation,
    capture_success_turn,
)
from orket.core.contracts.decision_inputs import SuccessEvaluationInput
from orket.decision_nodes.builtins import DefaultEvaluatorNode
from orket.schema import CardStatus, IssueConfig

pytestmark = pytest.mark.contract


@pytest.fixture(scope="module")
def prior_success_outcomes():
    return json.loads((Path(__file__).parents[1] / "fixtures/evaluator_success_v046.json").read_text(encoding="utf-8"))


def test_failure_context_is_deeply_detached_and_immutable():
    issue = IssueConfig(id="card", summary="Original", retry_count=1, max_retries=3)
    result = SimpleNamespace(error="Original", violations=["Original violation"])
    inputs = capture_failure_evaluation(issue, result)
    issue.retry_count, result.error = 2, "Changed"
    result.violations.clear()
    assert (inputs.retry_count, inputs.error, inputs.violations) == (1, "Original", ("Original violation",))
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.max_retries = 999
    with pytest.raises(AttributeError):
        inputs.violations.clear()


@pytest.mark.parametrize("initial", list(CardStatus))
@pytest.mark.parametrize("updated", [CardStatus.READY, CardStatus.CODE_REVIEW, CardStatus.DONE])
@pytest.mark.parametrize("review", [False, True])
def test_success_status_recommendations_preserve_the_existing_truth_table(initial, updated, review, prior_success_outcomes):
    issue = SimpleNamespace(id="card", status=initial)
    turn = SimpleNamespace(content="Decision captured")
    captured = capture_success_turn(issue, turn, "developer", review)
    inputs = SuccessEvaluationInput(turn=captured, updated_issue_status=updated)
    issue.status, turn.content = CardStatus.BLOCKED, "Changed externally"
    node = DefaultEvaluatorNode()
    expected = prior_success_outcomes["cases"]["|".join((initial.value, updated.value, str(review)))]
    assert node.evaluate_success(inputs) == expected
    assert node.evaluate_success(inputs) == node.evaluate_success(inputs.model_copy(deep=True))


def test_recommendations_are_detached_read_only_primitive_mappings():
    proposal = {"remember_decision": True}
    admitted = admit_success_recommendation(proposal)
    proposal["remember_decision"] = False
    assert admitted["remember_decision"] is True
    with pytest.raises(TypeError):
        admitted["remember_decision"] = False
    actions = admit_success_actions({"trigger_sandbox": True, "next_status": CardStatus.CODE_REVIEW})
    with pytest.raises(TypeError):
        actions["next_status"] = CardStatus.DONE
    assert actions["next_status"] == CardStatus.CODE_REVIEW


@pytest.mark.parametrize("payload", [{"remember_decision": []}, {"trigger_sandbox": "false"}, {"extra": True}])
def test_non_contract_success_values_are_refused(payload):
    with pytest.raises(ValidationError):
        admit_success_recommendation(payload)


def test_failure_recommendation_defaults_and_type_checks():
    inputs = capture_failure_evaluation(SimpleNamespace(id="card", retry_count=1, max_retries=3),
                                        SimpleNamespace(error="failure", violations=[]))
    assert admit_failure_recommendation({"action": "approval_pending"}, inputs).next_retry_count == 1
    for count in (True, "2", [], None):
        with pytest.raises(ValidationError):
            admit_failure_recommendation({"action": "retry", "next_retry_count": count}, inputs)
