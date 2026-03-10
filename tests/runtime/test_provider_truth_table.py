from __future__ import annotations

import pytest

from orket.runtime.provider_truth_table import (
    provider_truth_table_snapshot,
    validate_provider_truth_table,
)


# Layer: unit
def test_provider_truth_table_snapshot_has_expected_providers() -> None:
    payload = provider_truth_table_snapshot()
    assert payload["schema_version"] == "1.0"
    providers = [row["provider"] for row in payload["providers"]]
    assert providers == ["ollama", "openai_compat", "lmstudio"]


# Layer: contract
def test_provider_truth_table_capabilities_use_only_registered_states() -> None:
    payload = provider_truth_table_snapshot()
    allowed = {"supported", "conditional", "unsupported", "unknown"}
    for row in payload["providers"]:
        capabilities = row["capabilities"]
        assert capabilities
        for state in capabilities.values():
            assert state in allowed


# Layer: contract
def test_validate_provider_truth_table_returns_sorted_provider_names() -> None:
    assert validate_provider_truth_table() == ("lmstudio", "ollama", "openai_compat")


# Layer: contract
def test_validate_provider_truth_table_rejects_duplicate_provider_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import provider_truth_table as table

    monkeypatch.setattr(
        table,
        "_PROVIDER_TRUTH_ROWS",
        (
            {
                "provider": "ollama",
                "canonical_provider": "ollama",
                "capabilities": {"streaming": "supported"},
            },
            {
                "provider": "ollama",
                "canonical_provider": "ollama",
                "capabilities": {"streaming": "supported"},
            },
        ),
    )
    with pytest.raises(ValueError, match="E_PROVIDER_TRUTH_DUPLICATE_PROVIDER"):
        _ = table.validate_provider_truth_table()
