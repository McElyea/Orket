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
    assert "local_remote_route_policy_valid" in checks
    assert "failure_replay_harness_contract_valid" in checks
    assert "cold_start_truth_test_contract_valid" in checks
    assert "persistence_corruption_test_contract_valid" in checks
    assert "long_session_soak_test_contract_valid" in checks
    assert "resource_pressure_simulation_lane_valid" in checks
    assert "ui_lane_security_boundary_test_contract_valid" in checks
    assert "degradation_first_ui_standard_valid" in checks
    assert "naming_discipline_policy_valid" in checks
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


# Layer: contract
def test_runtime_truth_contract_drift_report_fails_when_persistence_corruption_contract_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    def _raise_contract_error() -> tuple[str, ...]:
        raise ValueError("E_PERSISTENCE_CORRUPTION_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")

    monkeypatch.setattr(
        checker,
        "validate_persistence_corruption_test_contract",
        _raise_contract_error,
    )
    payload = checker.runtime_truth_contract_drift_report()
    target = next(
        row for row in payload["checks"] if row["check"] == "persistence_corruption_test_contract_valid"
    )
    assert target["ok"] is False


# Layer: contract
def test_runtime_truth_contract_drift_report_fails_when_long_session_soak_contract_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    def _raise_contract_error() -> tuple[str, ...]:
        raise ValueError("E_LONG_SESSION_SOAK_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")

    monkeypatch.setattr(
        checker,
        "validate_long_session_soak_test_contract",
        _raise_contract_error,
    )
    payload = checker.runtime_truth_contract_drift_report()
    target = next(
        row for row in payload["checks"] if row["check"] == "long_session_soak_test_contract_valid"
    )
    assert target["ok"] is False


# Layer: contract
def test_runtime_truth_contract_drift_report_fails_when_resource_pressure_simulation_lane_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    def _raise_contract_error() -> tuple[str, ...]:
        raise ValueError("E_RESOURCE_PRESSURE_SIMULATION_LANE_CHECK_ID_SET_MISMATCH")

    monkeypatch.setattr(
        checker,
        "validate_resource_pressure_simulation_lane",
        _raise_contract_error,
    )
    payload = checker.runtime_truth_contract_drift_report()
    target = next(
        row for row in payload["checks"] if row["check"] == "resource_pressure_simulation_lane_valid"
    )
    assert target["ok"] is False


# Layer: contract
def test_runtime_truth_contract_drift_report_fails_when_ui_lane_security_boundary_test_contract_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    def _raise_contract_error() -> tuple[str, ...]:
        raise ValueError("E_UI_LANE_SECURITY_BOUNDARY_TEST_CONTRACT_CHECK_ID_SET_MISMATCH")

    monkeypatch.setattr(
        checker,
        "validate_ui_lane_security_boundary_test_contract",
        _raise_contract_error,
    )
    payload = checker.runtime_truth_contract_drift_report()
    target = next(
        row for row in payload["checks"] if row["check"] == "ui_lane_security_boundary_test_contract_valid"
    )
    assert target["ok"] is False


# Layer: contract
def test_runtime_truth_contract_drift_report_fails_when_degradation_first_ui_standard_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from orket.runtime import runtime_truth_drift_checker as checker

    def _raise_contract_error() -> tuple[str, ...]:
        raise ValueError("E_DEGRADATION_FIRST_UI_STANDARD_CHECK_ID_SET_MISMATCH")

    monkeypatch.setattr(
        checker,
        "validate_degradation_first_ui_standard",
        _raise_contract_error,
    )
    payload = checker.runtime_truth_contract_drift_report()
    target = next(
        row for row in payload["checks"] if row["check"] == "degradation_first_ui_standard_valid"
    )
    assert target["ok"] is False
