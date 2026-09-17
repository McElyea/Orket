"""Contract checks for transport decisions; live runtime proof is separate."""
import pytest
from pydantic import ValidationError

from orket.application.services.runtime_result_projection import (
    RuntimeCollectionResult,
    RuntimeExecutionResult,
    runtime_result_exit_code,
    runtime_result_lines,
)
from orket.core.contracts.runtime_execution_result import RuntimeCollectionMember
from tests.helpers.runtime_result import published_result

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("success", [True, False])
# Layer: contract
def test_published_result_projects_actual_classification(success):
    result = published_result(success=success, transcript=({"summary": "Everything worked!"},))
    assert result.succeeded is success
    assert runtime_result_exit_code(result) == (0 if success else 1)
    assert ("not successful" in runtime_result_lines(result)[0]) is (not success)


@pytest.mark.parametrize("observation", ["unresolved", "approval_pending", "cancelled"])
# Layer: contract
def test_nonpublication_cannot_promote_even_retained_success(observation):
    payload = published_result().model_dump(mode="json")
    result = RuntimeExecutionResult.model_validate({**payload, "observation": observation})
    assert not result.succeeded
    assert runtime_result_exit_code(result) == (130 if observation == "cancelled" else 1)


@pytest.mark.parametrize("damage", ["run", "final_truth", "publication_ref", "identity"])
# Layer: contract
def test_publication_rejects_missing_or_conflicting_authority(damage):
    payload = published_result().model_dump(mode="json")
    if damage == "identity":
        payload["final_truth"]["run_id"] = "other-run"
    else:
        payload[damage] = None
    with pytest.raises(ValidationError):
        RuntimeExecutionResult.model_validate(payload)


@pytest.mark.parametrize("value", [None, [], {"success": True}, "complete"])
# Layer: contract
def test_untyped_normal_returns_are_rejected(value):
    with pytest.raises(TypeError, match="TYPED_OUTCOME_REQUIRED"):
        runtime_result_exit_code(value)


@pytest.mark.parametrize("case", ["empty", "missing", "failed", "complete"])
# Layer: contract
def test_collection_requires_every_declared_success(case):
    members = () if case in {"empty", "missing"} else (
        RuntimeCollectionMember(target="one", result=published_result(success=case == "complete")),)
    result = RuntimeCollectionResult(session_id="group", build_id="group", collection="group",
        expected_members=() if case == "empty" else ("one",), members=members)
    assert result.succeeded is (case == "complete")
