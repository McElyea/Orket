"""Public Kernel admission and structural parity; comparison does not replay effects."""
from copy import deepcopy

import pytest

from orket.core.contracts.kernel_capability_policy import KernelCapabilityPolicy
from orket.core.contracts.kernel_run_inputs import CONTRACT_VERSION
from orket.kernel.v1 import validator
from tests.helpers.kernel_runtime import kernel_runtime as kernel_runtime


def _policy():
    return KernelCapabilityPolicy.from_payload({
        "contract_version": CONTRACT_VERSION, "policy_id": "kernel_capability_policy_v1",
        "policy_source": "controlled-policy", "policy_version": "1",
        "default_permissions": [], "role_task_permissions": {"tester": {"inspect": []}},
    })


@pytest.mark.contract
@pytest.mark.parametrize("operation", [
    validator.start_run_v1, validator.finish_run_v1, validator.resolve_capability_v1,
    validator.authorize_tool_call_v1, validator.replay_run_v1, validator.compare_runs_v1,
])
def test_public_operations_refuse_foreign_contract_version(operation):
    with pytest.raises(ValueError, match="contract_version must be kernel_api/v1"):
        operation({"contract_version": "foreign/v1"})


@pytest.mark.contract
@pytest.mark.parametrize("operation,payload,message", [
    (validator.finish_run_v1, {"run_handle": None}, "run_handle must be an object"),
    (validator.finish_run_v1, {"run_handle": {}}, "run_handle.run_id is required"),
    (validator.finish_run_v1, {"run_handle": {"run_id": "r"}}, "outcome must be PASS or FAIL"),
    (validator.resolve_capability_v1, {"task": "inspect"}, "role is required"),
    (validator.resolve_capability_v1, {"role": "tester"}, "task is required"),
    (validator.authorize_tool_call_v1, {"context": None}, "context must be an object"),
    (validator.authorize_tool_call_v1, {"context": {}}, "tool_request must be an object"),
])
def test_public_shape_errors_identify_the_missing_authority(operation, payload, message):
    with pytest.raises(ValueError, match=message):
        operation({"contract_version": CONTRACT_VERSION, **payload})


@pytest.mark.integration
@pytest.mark.usefixtures("kernel_runtime")
@pytest.mark.parametrize("changes,location", [
    ({"contract_version": "foreign/v1"}, "/contract_version"),
    ({"run_handle": None}, "/run_handle"),
    ({"turn_id": None}, "/turn_id"),
])
def test_turn_identity_refusal_precedes_workspace_effects(tmp_path, changes, location):
    result = validator.execute_turn_v1({
        "contract_version": CONTRACT_VERSION,
        "run_handle": {"run_id": "run-admission", "workspace_root": str(tmp_path)},
        "turn_id": "turn-1", "turn_input": {}, **changes,
    })
    assert result["outcome"] == "FAIL" and result["stage"] == "base_shape"
    assert result["issues"][0]["location"] == location
    assert result["errors"] == 1 and not list(tmp_path.iterdir())


@pytest.mark.integration
@pytest.mark.usefixtures("kernel_runtime")
@pytest.mark.parametrize("triplet", [
    None, {}, {"stem": 1, "body": {}, "links": {}},
    {"stem": "data/admitted", "body": [], "links": {}},
    {"stem": "data/admitted", "body": {}, "links": []},
    {"stem": "data/admitted", "body": {}, "links": {}, "manifest": []},
])
def test_invalid_triplet_never_stages_or_promotes_native_files(tmp_path, triplet):
    result = validator.execute_turn_v1({
        "contract_version": CONTRACT_VERSION,
        "run_handle": {"run_id": "run-admission", "workspace_root": str(tmp_path)},
        "turn_id": "turn-1", "turn_input": {"stage_triplet": triplet},
        "commit_intent": "stage_and_request_promotion",
    })
    assert result["outcome"] == "FAIL" and result["stage"] == "base_shape"
    assert result["issues"][0]["location"] == "/turn_input/stage_triplet"
    assert result["errors"] == 1 and not list(tmp_path.iterdir())


@pytest.mark.integration
@pytest.mark.usefixtures("kernel_runtime")
@pytest.mark.parametrize("context,tool,code", [
    ({"capability_resolved": False, "allow_tool_call": True}, {}, "E_CAPABILITY_NOT_RESOLVED"),
    ({"allow_tool_call": True}, {"side_effects_declared": False}, "E_SIDE_EFFECT_UNDECLARED"),
    ({"allow_tool_call": True}, {"requested_permissions": ["write"], "declared_permissions": ["read"]},
     "E_PERMISSION_DENIED"),
])
def test_capability_refusal_precedes_allow_hint_and_native_staging(tmp_path, context, tool, code):
    policy = _policy()
    decision = validator.authorize_tool_call_v1({
        "contract_version": CONTRACT_VERSION, "context": context, "tool_request": tool,
    }, policy_inputs=policy)["decision"]
    result = validator.execute_turn_v1({
        "contract_version": CONTRACT_VERSION,
        "run_handle": {"run_id": "run-admission", "workspace_root": str(tmp_path)},
        "turn_id": "turn-1", "turn_input": {"context": context, "tool_call": tool,
            "stage_triplet": {"stem": "data/admitted", "body": {}, "links": {}}},
        "commit_intent": "stage_and_request_promotion",
    }, policy_inputs=policy)
    assert decision["result"] == "DENY" and decision["reason_code"] == code
    assert result["outcome"] == "FAIL" and result["stage"] == "capability"
    assert result["capabilities"]["denied_count"] == 1
    assert result["issues"][0]["code"] == code and not list(tmp_path.iterdir())


@pytest.mark.contract
def test_explicit_disabled_capability_retains_its_distinct_decision():
    result = validator.authorize_tool_call_v1({
        "contract_version": CONTRACT_VERSION, "context": {"capability_enforcement": False},
        "tool_request": {"action": "tool.call", "resource": "tool://read"},
    }, policy_inputs=_policy())
    assert result["decision"]["result"] == "GRANT"
    assert result["decision"]["reason_code"] == "I_CAPABILITY_SKIPPED"
    assert result["decision"]["evidence"]["capability_source"] == "controlled-policy"


@pytest.mark.integration
@pytest.mark.usefixtures("kernel_runtime")
def test_malformed_optional_turn_tool_fields_still_deny_by_default(tmp_path):
    result = validator.execute_turn_v1({
        "contract_version": CONTRACT_VERSION,
        "run_handle": {"run_id": "run-admission", "workspace_root": str(tmp_path)},
        "turn_id": "turn-1", "turn_input": {"context": [], "tool_call": None},
    }, policy_inputs=_policy())
    assert result["outcome"] == "FAIL" and result["issues"][0]["code"] == "E_CAPABILITY_DENIED"
    assert not list(tmp_path.iterdir())


def _compare(left, right):
    return validator.compare_runs_v1({"contract_version": CONTRACT_VERSION, "run_a": left, "run_b": right})


@pytest.mark.contract
@pytest.mark.parametrize("payload", [None, [], "not an object"])
def test_replay_and_comparison_report_missing_descriptors(payload):
    replay = validator.replay_run_v1({"contract_version": CONTRACT_VERSION, "run_descriptor": payload})
    comparison = _compare(payload, {})
    for result in (replay, comparison):
        assert result["outcome"] == "FAIL" and result["turns_compared"] == 0
        assert result["issues"][0]["code"] == "E_REPLAY_INPUT_MISSING"


@pytest.mark.contract
def test_parity_filters_optional_rows_without_changing_inputs_or_executing_turns():
    clean = {"turn_digests": [{"turn_id": "t1", "turn_result_digest": "a" * 64, "evidence_digest": "b" * 64}],
        "stage_outcomes": [{"turn_id": "t1", "stage": "staging", "outcome": "PASS"}],
        "issues": [{"code": "E_TEST", "stage": "test", "location": "/x"}],
        "events": ["[INFO] [CODE:I_READY] [LOC:/] ready"]}
    noisy = deepcopy(clean)
    noisy["turn_digests"] += [None, {"turn_id": "", "turn_result_digest": "a" * 64},
                             {"turn_id": "invalid", "turn_result_digest": "short"}]
    noisy["stage_outcomes"] += [None, {"turn_id": "t2", "stage": "", "outcome": "PASS"}]
    noisy["issues"] += [None, {"code": "", "stage": "test", "location": "/x"}]
    noisy["events"] += [None, "ordinary prose", "[CODE:unterminated"]
    before = deepcopy(noisy)
    result = _compare(noisy, clean)
    assert result["outcome"] == "PASS" and result["turns_compared"] == 1
    assert result["parity"]["kind"] == "structural_parity" and result["parity"]["matches"] == 6
    assert noisy == before
    changed = deepcopy(clean)
    changed["turn_digests"][0]["evidence_digest"] = "c" * 64
    refused = _compare(clean, changed)
    assert refused["outcome"] == "FAIL" and refused["parity"]["mismatches"] == 1
    assert refused["issues"][0]["details"]["mismatch_fields"] == ["turn_digests"]


@pytest.mark.contract
@pytest.mark.parametrize("value", [None, {}, "omitted rows"])
def test_parity_normalizes_non_list_optional_surfaces(value):
    assert _compare({"turn_digests": value}, {"turn_digests": []})["outcome"] == "PASS"
