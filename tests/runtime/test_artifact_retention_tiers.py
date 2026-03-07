from __future__ import annotations

from pathlib import Path

import yaml


# Layer: contract
def test_artifact_retention_tiers_policy_exists_and_has_required_tiers() -> None:
    path = Path("core/policies/artifact_retention_tiers.yaml")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert "tier_1" in payload
    assert "tier_2" in payload
    assert "tier_3" in payload
    assert "run_summary.json" in list(payload["tier_1"])
    assert "tool_call.json" in list(payload["tier_2"])
