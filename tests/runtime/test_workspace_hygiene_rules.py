from __future__ import annotations

import pytest

from orket.runtime.workspace_hygiene_rules import (
    validate_workspace_hygiene_rules,
    workspace_hygiene_rules_snapshot,
)


# Layer: unit
def test_workspace_hygiene_rules_snapshot_contains_expected_rule_ids() -> None:
    payload = workspace_hygiene_rules_snapshot()
    assert payload["schema_version"] == "1.0"
    rule_ids = {row["rule_id"] for row in payload["rules"]}
    assert rule_ids == {"WSH-001", "WSH-002", "WSH-003", "WSH-004"}


# Layer: contract
def test_validate_workspace_hygiene_rules_accepts_current_snapshot() -> None:
    rule_ids = validate_workspace_hygiene_rules()
    assert "WSH-001" in rule_ids


# Layer: contract
def test_validate_workspace_hygiene_rules_rejects_rule_id_set_mismatch() -> None:
    payload = workspace_hygiene_rules_snapshot()
    payload["rules"] = [row for row in payload["rules"] if row["rule_id"] != "WSH-004"]
    with pytest.raises(ValueError, match="E_WORKSPACE_HYGIENE_RULES_RULE_ID_SET_MISMATCH"):
        _ = validate_workspace_hygiene_rules(payload)
