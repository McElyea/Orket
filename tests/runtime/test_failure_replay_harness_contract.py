from __future__ import annotations

import pytest

from orket.runtime.failure_replay_harness_contract import (
    failure_replay_harness_contract_snapshot,
    validate_failure_replay_harness_contract,
)


# Layer: unit
def test_failure_replay_harness_contract_snapshot_contains_expected_fields() -> None:
    payload = failure_replay_harness_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    required_inputs = set(payload["required_inputs"])
    required_outputs = set(payload["required_output_fields"])
    assert required_inputs == {"baseline_artifact", "candidate_artifact"}
    assert "drift" in required_outputs


# Layer: contract
def test_validate_failure_replay_harness_contract_accepts_current_snapshot() -> None:
    required_output_fields = validate_failure_replay_harness_contract()
    assert "difference_count" in required_output_fields


# Layer: contract
def test_validate_failure_replay_harness_contract_rejects_required_inputs_mismatch() -> None:
    payload = failure_replay_harness_contract_snapshot()
    payload["required_inputs"] = ["baseline_artifact"]
    with pytest.raises(ValueError, match="E_FAILURE_REPLAY_HARNESS_CONTRACT_REQUIRED_INPUTS_MISMATCH"):
        _ = validate_failure_replay_harness_contract(payload)
