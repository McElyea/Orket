from __future__ import annotations

import pytest

from orket.runtime.runtime_truth_drift_checker import (
    assert_no_runtime_truth_contract_drift,
    runtime_truth_contract_drift_report,
)


# Layer: unit
def test_runtime_truth_contract_drift_report_passes_for_current_contracts() -> None:
    payload = runtime_truth_contract_drift_report()
    assert payload["schema_version"] == "1.0"
    assert payload["ok"] is True
    assert len(payload["checks"]) >= 5
    checks = {row["check"] for row in payload["checks"]}
    assert "clock_time_authority_policy_valid" in checks
    assert "capability_fallback_hierarchy_valid" in checks
    assert "safe_default_catalog_valid" in checks


# Layer: contract
def test_assert_no_runtime_truth_contract_drift_returns_report_when_clean() -> None:
    payload = assert_no_runtime_truth_contract_drift()
    assert payload["ok"] is True


# Layer: contract
def test_assert_no_runtime_truth_contract_drift_raises_on_provider_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    monkeypatch.setattr(
        checker,
        "provider_truth_table_snapshot",
        lambda: {
            "schema_version": "1.0",
            "providers": [
                {"provider": "ollama"},
                {"provider": "openai_compat"},
            ],
        },
    )
    with pytest.raises(ValueError, match="E_RUNTIME_TRUTH_CONTRACT_DRIFT"):
        _ = checker.assert_no_runtime_truth_contract_drift()
