from __future__ import annotations

import pytest

from orket.runtime.source_attribution_policy import (
    source_attribution_policy_snapshot,
    validate_source_attribution_policy,
)


# Layer: unit
def test_source_attribution_policy_snapshot_contains_expected_modes() -> None:
    payload = source_attribution_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    modes = {row["mode"] for row in payload["modes"]}
    assert modes == {"optional", "required"}
    assert payload["required_claim_fields"] == ["claim_id", "claim", "source_ids"]
    assert payload["required_source_fields"] == ["source_id", "title", "uri", "kind"]


# Layer: contract
def test_validate_source_attribution_policy_accepts_current_snapshot() -> None:
    modes = validate_source_attribution_policy()
    assert "required" in modes


# Layer: contract
def test_validate_source_attribution_policy_rejects_mode_set_mismatch() -> None:
    payload = source_attribution_policy_snapshot()
    payload["modes"] = [row for row in payload["modes"] if row["mode"] != "required"]
    with pytest.raises(ValueError, match="E_SOURCE_ATTRIBUTION_POLICY_MODE_SET_MISMATCH"):
        _ = validate_source_attribution_policy(payload)
