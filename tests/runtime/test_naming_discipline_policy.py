from __future__ import annotations

import pytest

from orket.runtime.naming_discipline_policy import (
    naming_discipline_policy_snapshot,
    validate_naming_discipline_policy,
)


# Layer: unit
def test_naming_discipline_policy_snapshot_contains_expected_conventions() -> None:
    payload = naming_discipline_policy_snapshot()
    assert payload["schema_version"] == "1.0"
    convention_ids = {row["convention_id"] for row in payload["conventions"]}
    assert convention_ids == {
        "artifact_keys_snake_case",
        "artifact_filenames_match_keys",
        "governance_checker_scripts_snake_case",
    }


# Layer: contract
def test_validate_naming_discipline_policy_accepts_current_snapshot() -> None:
    convention_ids = validate_naming_discipline_policy()
    assert "artifact_keys_snake_case" in convention_ids


# Layer: contract
def test_validate_naming_discipline_policy_rejects_convention_set_mismatch() -> None:
    payload = naming_discipline_policy_snapshot()
    payload["conventions"] = [row for row in payload["conventions"] if row["convention_id"] != "artifact_keys_snake_case"]
    with pytest.raises(ValueError, match="E_NAMING_DISCIPLINE_POLICY_CONVENTION_SET_MISMATCH"):
        _ = validate_naming_discipline_policy(payload)
