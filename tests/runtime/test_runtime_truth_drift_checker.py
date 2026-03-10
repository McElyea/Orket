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
    assert "structured_warning_policy_valid" in checks
    assert "retry_classification_policy_valid" in checks
    assert "runtime_boundary_audit_checklist_valid" in checks
    assert "model_profile_bios_valid" in checks
    assert "interrupt_semantics_policy_valid" in checks
    assert "idempotency_discipline_policy_valid" in checks
    assert "artifact_provenance_block_policy_valid" in checks
    assert "operator_override_logging_policy_valid" in checks
    assert "demo_production_labeling_policy_valid" in checks
    assert "human_correction_capture_policy_valid" in checks
    assert "sampling_discipline_guide_valid" in checks
    assert "execution_readiness_rubric_valid" in checks
    assert "release_confidence_scorecard_valid" in checks
    assert "feature_flag_expiration_policy_valid" in checks
    assert "workspace_hygiene_rules_valid" in checks
    assert "canonical_examples_library_valid" in checks
    assert "spec_debt_queue_valid" in checks
    assert "non_fatal_error_budget_valid" in checks
    assert "interface_freeze_windows_valid" in checks
    assert "evidence_package_generator_contract_valid" in checks
    assert "observability_redaction_test_contract_valid" in checks
    assert "trust_language_review_policy_valid" in checks
    assert "promotion_rollback_criteria_valid" in checks


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
