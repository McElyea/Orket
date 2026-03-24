from __future__ import annotations

import pytest

from orket.runtime.protocol_error_codes import E_NAMESPACE_POLICY_VIOLATION_PREFIX
from orket.runtime.tool_invocation_policy_contract import (
    tool_invocation_policy_contract_snapshot,
    validate_tool_invocation_policy_contract,
)


# Layer: unit
def test_tool_invocation_policy_contract_snapshot_contains_epic_policy() -> None:
    payload = tool_invocation_policy_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    policies = list(payload["policies"])
    assert len(policies) == 1
    assert policies[0]["run_type"] == "epic"
    assert policies[0]["namespace_scope_rule"] == "run_scope_only"
    assert E_NAMESPACE_POLICY_VIOLATION_PREFIX in policies[0]["required_error_codes"]
    assert policies[0]["tool_to_tool_invocation"] == "disallow"


# Layer: contract
def test_validate_tool_invocation_policy_contract_accepts_current_snapshot() -> None:
    run_types = validate_tool_invocation_policy_contract()
    assert "epic" in run_types


# Layer: contract
def test_validate_tool_invocation_policy_contract_rejects_unregistered_error_code() -> None:
    payload = tool_invocation_policy_contract_snapshot()
    payload["policies"][0]["required_error_codes"] = ["E_NOT_REGISTERED"]
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_POLICY_CONTRACT_REQUIRED_ERROR_CODE_UNREGISTERED"):
        _ = validate_tool_invocation_policy_contract(payload)


# Layer: contract
def test_validate_tool_invocation_policy_contract_rejects_run_type_set_mismatch() -> None:
    payload = tool_invocation_policy_contract_snapshot()
    payload["policies"][0]["run_type"] = "maintenance"
    with pytest.raises(ValueError, match="E_TOOL_INVOCATION_POLICY_CONTRACT_RUN_TYPE_SET_MISMATCH"):
        _ = validate_tool_invocation_policy_contract(payload)
