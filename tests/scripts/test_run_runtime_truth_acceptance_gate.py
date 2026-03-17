from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.run_runtime_truth_acceptance_gate import (
    REQUIRED_RUNTIME_CONTRACT_FILES,
    evaluate_runtime_truth_acceptance_gate,
    main,
)


def _write_contract_set(workspace: Path, run_id: str) -> Path:
    contracts_dir = workspace / "observability" / run_id / "runtime_contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_RUNTIME_CONTRACT_FILES:
        (contracts_dir / filename).write_text(
            json.dumps({"schema_version": "1.0"}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return contracts_dir


# Layer: integration
def test_runtime_truth_acceptance_gate_passes_with_drift_and_contract_files(tmp_path: Path) -> None:
    _write_contract_set(tmp_path, "run-ok")
    exit_code = main(["--workspace", str(tmp_path), "--run-id", "run-ok"])
    assert exit_code == 0


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_required_contract_file_missing(tmp_path: Path) -> None:
    contracts_dir = _write_contract_set(tmp_path, "run-missing")
    (contracts_dir / REQUIRED_RUNTIME_CONTRACT_FILES[0]).unlink()

    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="run-missing",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_contract_files_missing" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_can_run_drift_check_without_run_id(tmp_path: Path) -> None:
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=True,
    )
    assert payload["ok"] is True
    assert payload["details"]["drift_report"]["ok"] is True
    assert payload["details"]["unreachable_branch_check"]["ok"] is True
    assert payload["details"]["noop_critical_path_check"]["ok"] is True
    assert payload["details"]["environment_parity_check"]["ok"] is True
    assert payload["details"]["runtime_invariant_registry_check"]["ok"] is True
    assert payload["details"]["runtime_config_ownership_map_check"]["ok"] is True
    assert payload["details"]["unknown_input_policy_check"]["ok"] is True
    assert payload["details"]["clock_time_authority_policy_check"]["ok"] is True
    assert payload["details"]["capability_fallback_hierarchy_check"]["ok"] is True
    assert payload["details"]["runtime_truth_foundation_contracts_check"]["ok"] is True
    assert payload["details"]["structured_warning_policy_check"]["ok"] is True
    assert payload["details"]["retry_classification_policy_check"]["ok"] is True
    assert payload["details"]["provider_quarantine_policy_check"]["ok"] is True
    assert payload["details"]["safe_default_catalog_check"]["ok"] is True
    assert payload["details"]["runtime_boundary_audit_check"]["ok"] is True
    assert payload["details"]["model_profile_bios_check"]["ok"] is True
    assert payload["details"]["interrupt_semantics_policy_check"]["ok"] is True
    assert payload["details"]["idempotency_discipline_policy_check"]["ok"] is True
    assert payload["details"]["result_error_invariant_check"]["ok"] is True
    assert payload["details"]["artifact_provenance_block_policy_check"]["ok"] is True
    assert payload["details"]["narration_effect_audit_policy_check"]["ok"] is True
    assert payload["details"]["source_attribution_policy_check"]["ok"] is True
    assert payload["details"]["operator_override_logging_policy_check"]["ok"] is True
    assert payload["details"]["demo_production_labeling_policy_check"]["ok"] is True
    assert payload["details"]["human_correction_capture_policy_check"]["ok"] is True
    assert payload["details"]["sampling_discipline_guide_check"]["ok"] is True
    assert payload["details"]["execution_readiness_rubric_check"]["ok"] is True
    assert payload["details"]["release_confidence_scorecard_check"]["ok"] is True
    assert payload["details"]["feature_flag_expiration_policy_check"]["ok"] is True
    assert payload["details"]["workspace_hygiene_rules_check"]["ok"] is True
    assert payload["details"]["canonical_examples_library_check"]["ok"] is True
    assert payload["details"]["spec_debt_queue_check"]["ok"] is True
    assert payload["details"]["non_fatal_error_budget_check"]["ok"] is True
    assert payload["details"]["interface_freeze_windows_check"]["ok"] is True
    assert payload["details"]["evidence_package_generator_contract_check"]["ok"] is True
    assert payload["details"]["conformance_governance_contract_check"]["ok"] is True
    assert payload["details"]["observability_redaction_tests_check"]["ok"] is True
    assert payload["details"]["trust_language_review_check"]["ok"] is True
    assert payload["details"]["local_remote_route_policy_check"]["ok"] is True
    assert payload["details"]["tool_invocation_policy_contract_check"]["ok"] is True
    assert payload["details"]["failure_replay_harness_contract_check"]["ok"] is True
    assert payload["details"]["cold_start_truth_tests_check"]["ok"] is True
    assert payload["details"]["persistence_corruption_tests_check"]["ok"] is True
    assert payload["details"]["long_session_soak_tests_check"]["ok"] is True
    assert payload["details"]["resource_pressure_simulation_lane_check"]["ok"] is True
    assert payload["details"]["ui_lane_security_boundary_tests_check"]["ok"] is True
    assert payload["details"]["degradation_first_ui_standard_check"]["ok"] is True
    assert payload["details"]["decision_record_operating_principles_contract_check"]["ok"] is True
    assert payload["details"]["naming_discipline_policy_check"]["ok"] is True
    assert payload["details"]["promotion_rollback_criteria_check"]["ok"] is True


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_unreachable_branch_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_unreachable_branches",
        lambda *, roots: {
            "schema_version": "1.0",
            "ok": False,
            "findings": [{"path": "x.py", "line": 1}],
            "parse_errors": [],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "unreachable_branch_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_noop_critical_path_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_noop_critical_paths",
        lambda *, roots: {
            "schema_version": "1.0",
            "ok": False,
            "findings": [{"path": "x.py", "line": 1, "name": "noop"}],
            "parse_errors": [],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "noop_critical_path_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_environment_parity_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_environment_parity_checklist",
        lambda *, environment, required_keys: {
            "schema_version": "1.0",
            "ok": False,
            "checks": [{"check": "required_env_keys_present", "ok": False}],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "environment_parity_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_runtime_invariant_registry_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_runtime_invariant_registry",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "invariant_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_invariant_registry_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_runtime_config_ownership_map_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_runtime_config_ownership_map",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "config_key_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_config_ownership_map_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_unknown_input_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_unknown_input_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "unknown_input_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_clock_time_authority_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_clock_time_authority_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "defaults": {},
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "clock_time_authority_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_capability_fallback_hierarchy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_capability_fallback_hierarchy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "capability_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "capability_fallback_hierarchy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_runtime_truth_foundation_contracts_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_runtime_truth_foundation_contracts",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "checks": [{"check": "runtime_status_vocabulary_contract_valid", "ok": False}],
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_truth_foundation_contracts_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_warning_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_structured_warning_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "warning_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "structured_warning_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_retry_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_retry_classification_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "signal_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "retry_classification_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_provider_quarantine_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_provider_quarantine_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "env_key_count": 0,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "provider_quarantine_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_safe_default_catalog_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_safe_default_catalog",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "default_key_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "safe_default_catalog_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_boundary_audit_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_runtime_boundary_audit_checklist",
        lambda *, workspace: {
            "schema_version": "1.0",
            "ok": False,
            "boundary_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_boundary_audit_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_model_profile_bios_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_model_profile_bios",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "profile_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "model_profile_bios_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_interrupt_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_interrupt_semantics_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "interrupt_semantics_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_idempotency_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_idempotency_discipline_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "idempotency_discipline_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_result_error_invariant_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_result_error_invariants",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "forbidden_status_count": 0,
            "behavior_case_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "result_error_invariant_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_artifact_provenance_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_artifact_provenance_block_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "required_field_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "artifact_provenance_block_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_operator_override_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_operator_override_logging_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "override_type_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "operator_override_logging_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_demo_production_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_demo_production_labeling_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "label_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "demo_production_labeling_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_human_correction_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_human_correction_capture_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "target_surface_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "human_correction_capture_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_sampling_discipline_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_sampling_discipline_guide",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "event_class_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "sampling_discipline_guide_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_execution_readiness_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_execution_readiness_rubric",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "criteria_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "execution_readiness_rubric_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_release_confidence_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_release_confidence_scorecard",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "dimension_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "release_confidence_scorecard_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_feature_flag_expiration_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_feature_flag_expiration_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "required_field_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "feature_flag_expiration_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_workspace_hygiene_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_workspace_hygiene_rules",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "rule_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "workspace_hygiene_rules_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_canonical_examples_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_canonical_examples_library",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "example_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "canonical_examples_library_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_spec_debt_queue_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_spec_debt_queue",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "debt_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "spec_debt_queue_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_non_fatal_error_budget_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_non_fatal_error_budget",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "budget_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "non_fatal_error_budget_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_interface_freeze_windows_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_interface_freeze_windows",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "window_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "interface_freeze_windows_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_evidence_package_generator_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_evidence_package_generator_contract",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "required_section_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "evidence_package_generator_contract_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_conformance_governance_contract_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_conformance_governance_contract",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "section_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "conformance_governance_contract_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_observability_redaction_tests_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_observability_redaction_tests",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "observability_redaction_tests_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_trust_language_review_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_trust_language_review",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "claim_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "trust_language_review_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_local_remote_route_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_local_remote_route_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "lane_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "local_remote_route_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_tool_invocation_policy_contract_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_tool_invocation_policy_contract",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "run_type_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "tool_invocation_policy_contract_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_failure_replay_harness_contract_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_failure_replay_harness_contract",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "required_output_field_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "failure_replay_harness_contract_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_cold_start_truth_tests_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_cold_start_truth_tests",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "cold_start_truth_tests_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_persistence_corruption_tests_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_persistence_corruption_test_suite",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "persistence_corruption_tests_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_long_session_soak_tests_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_long_session_soak_tests",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
            "turn_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "long_session_soak_tests_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_resource_pressure_simulation_lane_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_resource_pressure_simulation_lane",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "resource_pressure_simulation_lane_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_ui_lane_security_boundary_tests_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_ui_lane_security_boundary_tests",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "ui_lane_security_boundary_tests_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_degradation_first_ui_standard_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_degradation_first_ui_standard",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "degradation_first_ui_standard_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_decision_record_operating_principles_contract_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_decision_record_operating_principles_contract",
        lambda *, workspace: {
            "schema_version": "1.0",
            "ok": False,
            "check_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "decision_record_operating_principles_contract_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_naming_discipline_policy_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_naming_discipline_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "convention_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "naming_discipline_policy_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_promotion_rollback_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import run_runtime_truth_acceptance_gate as gate

    monkeypatch.setattr(
        gate,
        "evaluate_promotion_rollback_criteria",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "trigger_count": 0,
        },
    )
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "promotion_rollback_criteria_check_failed" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_required_file_list_tracks_new_contract_artifacts() -> None:
    assert "runtime_invariant_registry.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "runtime_config_ownership_map.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "unknown_input_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "clock_time_authority_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "provider_quarantine_policy_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "safe_default_catalog.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "capability_fallback_hierarchy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "model_profile_bios.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "interrupt_semantics_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "retry_classification_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "runtime_boundary_audit_checklist.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "idempotency_discipline_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "result_error_invariant_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "artifact_provenance_block_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "narration_effect_audit_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "source_attribution_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "operator_override_logging_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "demo_production_labeling_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "human_correction_capture_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "sampling_discipline_guide.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "execution_readiness_rubric.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "release_confidence_scorecard.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "feature_flag_expiration_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "workspace_hygiene_rules.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "canonical_examples_library.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "spec_debt_queue.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "non_fatal_error_budget.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "interface_freeze_windows.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "evidence_package_generator_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "conformance_governance_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "observability_redaction_test_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "trust_language_review_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "local_remote_route_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "failure_replay_harness_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "cold_start_truth_test_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "persistence_corruption_test_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "long_session_soak_test_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "resource_pressure_simulation_lane.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "ui_lane_security_boundary_test_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "degradation_first_ui_standard.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "decision_record_operating_principles_contract.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "naming_discipline_policy.json" in REQUIRED_RUNTIME_CONTRACT_FILES
    assert "promotion_rollback_criteria.json" in REQUIRED_RUNTIME_CONTRACT_FILES
