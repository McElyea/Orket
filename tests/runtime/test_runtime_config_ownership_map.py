from __future__ import annotations

import pytest

from orket.runtime.runtime_config_ownership_map import (
    runtime_config_ownership_map_snapshot,
    validate_runtime_config_ownership_map,
)


# Layer: unit
def test_runtime_config_ownership_map_snapshot_contains_expected_key() -> None:
    payload = runtime_config_ownership_map_snapshot()
    assert payload["schema_version"] == "1.0"
    keys = {row["config_key"] for row in payload["rows"]}
    assert "ORKET_STATE_BACKEND_MODE" in keys
    assert "ORKET_PROVIDER_QUARANTINE" in keys


# Layer: contract
def test_validate_runtime_config_ownership_map_returns_sorted_keys() -> None:
    keys = validate_runtime_config_ownership_map()
    assert "ORKET_STATE_BACKEND_MODE" in keys
    assert "ORKET_PROVIDER_MODEL_QUARANTINE" in keys


# Layer: contract
def test_validate_runtime_config_ownership_map_rejects_duplicate_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_config_ownership_map as mapping

    monkeypatch.setattr(
        mapping,
        "_CONFIG_OWNERSHIP_ROWS",
        (
            {"config_key": "ORKET_A", "owner": "a.py", "domain": "a"},
            {"config_key": "ORKET_A", "owner": "b.py", "domain": "b"},
        ),
    )
    with pytest.raises(ValueError, match="E_RUNTIME_CONFIG_OWNERSHIP_DUPLICATE_KEY"):
        _ = mapping.validate_runtime_config_ownership_map()
