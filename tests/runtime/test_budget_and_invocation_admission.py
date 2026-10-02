"""Structural policy admission only; no promotion or tool execution claims."""
from copy import deepcopy

import pytest

from orket.runtime.policy.non_fatal_error_budget import (
    non_fatal_error_budget_snapshot,
    validate_non_fatal_error_budget,
)
from orket.runtime.policy.tool_invocation_policy_contract import (
    tool_invocation_policy_contract_snapshot,
    validate_tool_invocation_policy_contract,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("path,value,error", [
    (("budgets",), [], "EMPTY"), (("budgets", 0), [], "ROW_SCHEMA"),
    (("budgets", 0, "budget_id"), " ", "ID_REQUIRED"),
    (("budgets", 0, "metric"), " ", "METRIC_REQUIRED"),
    (("budgets", 0, "max_fraction"), "invalid", "MAX_FRACTION_INVALID"),
    (("budgets", 0, "max_fraction"), 0, "MAX_FRACTION_RANGE"),
    (("budgets", 0, "max_fraction"), 1, "MAX_FRACTION_RANGE"),
    (("budgets", 0, "breach_action"), "ignore", "BREACH_ACTION_INVALID"),
    (("budgets", 0, "budget_id"), "repair_applied_ratio", "DUPLICATE_ID"),
    (("evaluation_window",), None, "WINDOW_SCHEMA"),
    (("evaluation_window", "lookback_runs"), "bad", "LOOKBACK_RUNS_INVALID"),
    (("evaluation_window", "window_hours"), 0, "WINDOW_HOURS_INVALID"),
    (("evaluation_window", "min_distinct_runs"), None, "MIN_DISTINCT_RUNS_INVALID"),
    (("escalation_policy",), [], "ESCALATION_POLICY_SCHEMA"),
    (("escalation_policy", "consecutive_breaches_for_escalation"), 1, "CONSECUTIVE_BREACHES_RANGE"),
    (("escalation_policy", "escalation_action"), "ignore", "ESCALATION_ACTION_INVALID"),
])
def test_error_budget_refuses_invalid_identity_bounds_and_authority(path, value, error):
    payload = non_fatal_error_budget_snapshot()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_NON_FATAL_ERROR_BUDGET_" + error):
        validate_non_fatal_error_budget(payload)
    assert payload == before


@pytest.mark.parametrize("field,value,error", [
    ("run_type", " ", "RUN_TYPE_REQUIRED"), ("route_lane", " ", "ROUTE_LANE_REQUIRED"),
    ("allowed_tool_rings", [], "RINGS_EMPTY"),
    ("allowed_tool_rings", ["unsupported"], "RING_INVALID"),
    ("allowed_capability_profiles", [], "CAPABILITY_PROFILES_EMPTY"),
    ("allowed_capability_profiles", ["unbounded"], "CAPABILITY_PROFILE_INVALID"),
    ("namespace_scope_rule", "global", "NAMESPACE_SCOPE_RULE_INVALID"),
    ("run_determinism_class", "random", "DETERMINISM_CLASS_INVALID"),
    ("tool_to_tool_invocation", "allow", "TOOL_TO_TOOL_POLICY_INVALID"),
    ("max_tool_invocations_per_run", 0, "MAX_INVOCATIONS_INVALID"),
    ("required_error_codes", [], "REQUIRED_ERROR_CODES_EMPTY"),
    ("required_error_codes", ["E_UNREGISTERED_TEST_CODE"], "REQUIRED_ERROR_CODE_UNREGISTERED"),
])
def test_invocation_policy_refuses_undeclared_or_unbounded_execution(field, value, error):
    payload = tool_invocation_policy_contract_snapshot()
    payload["policies"][0][field] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_POLICY_CONTRACT_" + error):
        validate_tool_invocation_policy_contract(payload)
    assert payload == before


@pytest.mark.parametrize("case,error", [("empty", "EMPTY"), ("nonobject", "ROW_SCHEMA"),
                                       ("duplicate", "DUPLICATE_RUN_TYPE")])
def test_invocation_policy_requires_distinct_nonempty_objects(case, error):
    payload = tool_invocation_policy_contract_snapshot()
    payload["policies"] = [] if case == "empty" else [None] if case == "nonobject" else payload["policies"] * 2
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_POLICY_CONTRACT_" + error):
        validate_tool_invocation_policy_contract(payload)
    assert payload == before
