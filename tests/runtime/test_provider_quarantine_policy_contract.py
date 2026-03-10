from __future__ import annotations

import pytest

from orket.runtime.provider_quarantine_policy_contract import (
    provider_quarantine_policy_contract_snapshot,
    validate_provider_quarantine_policy_contract,
)


# Layer: contract
def test_provider_quarantine_policy_contract_snapshot_contains_expected_env_keys() -> None:
    payload = provider_quarantine_policy_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["env_keys"] == [
        "ORKET_PROVIDER_MODEL_QUARANTINE",
        "ORKET_PROVIDER_QUARANTINE",
    ]


# Layer: contract
def test_validate_provider_quarantine_policy_contract_accepts_current_snapshot() -> None:
    env_keys = validate_provider_quarantine_policy_contract()
    assert env_keys == (
        "ORKET_PROVIDER_MODEL_QUARANTINE",
        "ORKET_PROVIDER_QUARANTINE",
    )


# Layer: contract
def test_validate_provider_quarantine_policy_contract_rejects_env_key_mismatch() -> None:
    payload = provider_quarantine_policy_contract_snapshot()
    payload["env_keys"] = ["ORKET_PROVIDER_QUARANTINE"]
    with pytest.raises(ValueError, match="E_PROVIDER_QUARANTINE_POLICY_CONTRACT_ENV_KEYS_MISMATCH"):
        _ = validate_provider_quarantine_policy_contract(payload)
