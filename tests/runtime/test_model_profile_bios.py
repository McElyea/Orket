from __future__ import annotations

import pytest

from orket.runtime.model_profile_bios import model_profile_bios_snapshot, validate_model_profile_bios


# Layer: unit
def test_model_profile_bios_snapshot_contains_expected_profiles() -> None:
    payload = model_profile_bios_snapshot()
    assert payload["schema_version"] == "1.0"
    providers = {row["provider"] for row in payload["profiles"]}
    assert providers == {"ollama", "openai_compat", "lmstudio"}


# Layer: contract
def test_validate_model_profile_bios_accepts_current_snapshot() -> None:
    profile_ids = validate_model_profile_bios()
    assert "ollama-default" in profile_ids


# Layer: contract
def test_validate_model_profile_bios_rejects_provider_set_mismatch() -> None:
    payload = model_profile_bios_snapshot()
    payload["profiles"] = [row for row in payload["profiles"] if row["provider"] != "lmstudio"]
    with pytest.raises(ValueError, match="E_MODEL_PROFILE_BIOS_PROVIDER_SET_MISMATCH"):
        _ = validate_model_profile_bios(payload)
