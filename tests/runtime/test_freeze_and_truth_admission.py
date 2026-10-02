"""Contract admission of policy declarations; these tests do not execute their gates."""
from copy import deepcopy

import pytest

from orket.runtime.policy.interface_freeze_windows import (
    interface_freeze_windows_snapshot,
    validate_interface_freeze_windows,
)
from orket.runtime.policy.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
    validate_degradation_taxonomy_contract,
    validate_fail_behavior_registry_contract,
    validate_runtime_status_vocabulary_contract,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("path,value,error", [
    (("windows",), [], "EMPTY"),
    (("windows", 0), [], "ROW_SCHEMA"),
    (("windows", 0, "window_id"), " ", "ID_REQUIRED"),
    (("windows", 0, "scope"), " ", "SCOPE_REQUIRED"),
    (("windows", 0, "duration_hours"), "invalid", "DURATION_INVALID"),
    (("windows", 0, "duration_hours"), 0, "DURATION_INVALID"),
    (("windows", 0, "blocked_change_classes"), [], "BLOCKED_CHANGE_CLASSES_EMPTY"),
    (("windows", 0, "blocked_change_classes"), [" "], "BLOCKED_CHANGE_CLASS_INVALID"),
    (("windows", 0, "blocked_change_classes"), ["same", " same "], "BLOCKED_CHANGE_CLASS_DUPLICATE"),
    (("windows", 0, "override_policy"), "automatic", "OVERRIDE_POLICY_INVALID"),
    (("windows", 0, "window_id"), "promotion_candidate_interface_freeze", "DUPLICATE_ID"),
    (("emergency_break_policy",), [], "EMERGENCY_POLICY_SCHEMA"),
    (("emergency_break_policy", "override_log_required"), False, "OVERRIDE_LOG_REQUIRED"),
    (("emergency_break_policy", "required_override_fields"), [], "OVERRIDE_FIELDS_MISMATCH"),
    (("emergency_break_policy", "max_break_glass_duration_hours"), 9, "BREAK_GLASS_DURATION_RANGE"),
    (("emergency_break_policy", "max_break_glass_duration_hours"), None, "BREAK_GLASS_DURATION_INVALID"),
])
def test_freeze_admission_preserves_rejected_policy(path, value, error):
    payload = interface_freeze_windows_snapshot()
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_INTERFACE_FREEZE_WINDOWS_" + error):
        validate_interface_freeze_windows(payload)
    assert payload == before


@pytest.mark.parametrize("terms,error", [
    ({"running": True}, "EMPTY"), ([" "], "EMPTY"),
    (["running", " RUNNING "], "DUPLICATE"), (["running", "fictional"], "SET_MISMATCH"),
])
def test_runtime_vocabulary_refuses_missing_duplicate_or_invented_status(terms, error):
    payload = runtime_status_vocabulary_snapshot()
    payload["runtime_status_terms"] = terms
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_RUNTIME_STATUS_VOCABULARY_" + error):
        validate_runtime_status_vocabulary_contract(payload)
    assert payload == before


@pytest.mark.parametrize("case,error", [
    ("nonlist", "EMPTY"), ("nonobject", "EMPTY"), ("missing-description", "ROW_SCHEMA"),
    ("duplicate", "DUPLICATE_LEVEL"), ("unknown", "LEVEL_SET_MISMATCH"),
])
def test_degradation_declarations_require_distinct_complete_levels(case, error):
    payload = degradation_taxonomy_snapshot()
    if case == "nonlist":
        payload["levels"] = {}
    elif case == "nonobject":
        payload["levels"] = ["none"]
    elif case == "missing-description":
        payload["levels"][0]["description"] = " "
    elif case == "duplicate":
        payload["levels"].append(deepcopy(payload["levels"][0]))
    else:
        payload["levels"][0]["level"] = "unknown"
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_DEGRADATION_TAXONOMY_" + error):
        validate_degradation_taxonomy_contract(payload)
    assert payload == before


@pytest.mark.parametrize("case,error", [
    ("empty", "EMPTY"), ("missing-reason", "ROW_SCHEMA"), ("invalid-mode", "MODE_INVALID"),
    ("duplicate", "DUPLICATE_SUBSYSTEM"), ("missing-mode", "MODE_SET_MISMATCH"),
])
def test_fail_behavior_registry_refuses_ambiguous_subsystems_and_modes(case, error):
    payload = fail_behavior_registry_snapshot()
    if case == "empty":
        payload["subsystems"] = []
    elif case == "missing-reason":
        payload["subsystems"][0]["reason"] = " "
    elif case == "invalid-mode":
        payload["subsystems"][0]["failure_mode"] = "pretend_success"
    elif case == "duplicate":
        payload["subsystems"].append(deepcopy(payload["subsystems"][0]))
    else:
        payload["subsystems"] = [row for row in payload["subsystems"] if row["failure_mode"] == "fail_open"]
    before = deepcopy(payload)
    with pytest.raises(ValueError, match="E_FAIL_BEHAVIOR_REGISTRY_" + error):
        validate_fail_behavior_registry_contract(payload)
    assert payload == before
