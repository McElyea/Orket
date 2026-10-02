"""Structural readiness declaration admission; this does not establish readiness."""
from copy import deepcopy

import pytest

from orket.runtime.policy.execution_readiness_rubric import (
    execution_readiness_rubric_snapshot,
    validate_execution_readiness_rubric,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("path,value,error", [
    (("minimum_score",), "0.9", "MIN_SCORE_SCHEMA"),
    (("minimum_score",), -1, "MIN_SCORE_RANGE"),
    (("criteria",), [], "CRITERIA_EMPTY"),
    (("criteria", 0), [], "ROW_SCHEMA"),
    (("criteria", 0, "criterion"), " ", "CRITERION_REQUIRED"),
    (("criteria", 0, "weight"), "0.3", "WEIGHT_SCHEMA"),
    (("criteria", 0, "weight"), 0, "WEIGHT_RANGE"),
    (("criteria", 0, "weight"), 0.1, "WEIGHT_TOTAL_INVALID"),
    (("criteria", 0, "severity"), "ignore", "SEVERITY_INVALID"),
    (("criteria", 0, "criterion"), "acceptance_gate_green", "DUPLICATE_CRITERION"),
])
def test_readiness_admission_refuses_ambiguous_or_malformed_criteria(path, value, error):
    payload = execution_readiness_rubric_snapshot()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_EXECUTION_READINESS_RUBRIC_" + error):
        validate_execution_readiness_rubric(payload)
    assert payload == before
