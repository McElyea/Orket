from __future__ import annotations

import pytest

from orket.runtime.safe_default_catalog import safe_default_catalog_snapshot, validate_safe_default_catalog


# Layer: unit
def test_safe_default_catalog_snapshot_contains_expected_defaults() -> None:
    payload = safe_default_catalog_snapshot()
    assert payload["schema_version"] == "1.0"
    keys = {row["default_key"] for row in payload["defaults"]}
    assert "protocol_timezone" in keys
    assert "provider_runtime_target.default_provider" in keys


# Layer: contract
def test_validate_safe_default_catalog_accepts_current_snapshot() -> None:
    keys = validate_safe_default_catalog()
    assert "unknown_provider_input.on_unknown" in keys


# Layer: contract
def test_validate_safe_default_catalog_rejects_unknown_provider_non_fail_closed() -> None:
    payload = safe_default_catalog_snapshot()
    for row in payload["defaults"]:
        if row["default_key"] == "unknown_provider_input.on_unknown":
            row["default_value"] = "degrade"
    with pytest.raises(ValueError, match="E_SAFE_DEFAULT_CATALOG_PROVIDER_UNKNOWN_NOT_FAIL_CLOSED"):
        _ = validate_safe_default_catalog(payload)
