from __future__ import annotations

import yaml

from orket.runtime.config.contract_assets import ARTIFACT_RETENTION_TIERS_PATH


# Layer: contract
def test_artifact_retention_tiers_policy_exists_and_has_required_tiers() -> None:
    path = ARTIFACT_RETENTION_TIERS_PATH
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert "tier_1" in payload
    assert "tier_2" in payload
    assert "tier_3" in payload
    assert "run_summary.json" in list(payload["tier_1"])
    assert "tool_call.json" in list(payload["tier_2"])
