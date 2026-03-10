from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.runtime_truth_drift_checker import runtime_truth_contract_drift_report
from scripts.governance.check_artifact_provenance_block_policy import (
    evaluate_artifact_provenance_block_policy,
)
from scripts.governance.check_demo_production_labeling_policy import (
    evaluate_demo_production_labeling_policy,
)
from scripts.governance.check_noop_critical_paths import (
    DEFAULT_SCAN_ROOTS as DEFAULT_NOOP_SCAN_ROOTS,
    evaluate_noop_critical_paths,
)
from scripts.governance.check_environment_parity_checklist import evaluate_environment_parity_checklist
from scripts.governance.check_idempotency_discipline_policy import (
    evaluate_idempotency_discipline_policy,
)
from scripts.governance.check_interrupt_semantics_policy import evaluate_interrupt_semantics_policy
from scripts.governance.check_model_profile_bios import evaluate_model_profile_bios
from scripts.governance.check_human_correction_capture_policy import (
    evaluate_human_correction_capture_policy,
)
from scripts.governance.check_sampling_discipline_guide import (
    evaluate_sampling_discipline_guide,
)
from scripts.governance.check_execution_readiness_rubric import (
    evaluate_execution_readiness_rubric,
)
from scripts.governance.check_release_confidence_scorecard import (
    evaluate_release_confidence_scorecard,
)
from scripts.governance.check_feature_flag_expiration_policy import (
    evaluate_feature_flag_expiration_policy,
)
from scripts.governance.check_workspace_hygiene_rules import (
    evaluate_workspace_hygiene_rules,
)
from scripts.governance.check_canonical_examples_library import (
    evaluate_canonical_examples_library,
)
from scripts.governance.check_spec_debt_queue import (
    evaluate_spec_debt_queue,
)
from scripts.governance.check_non_fatal_error_budget import (
    evaluate_non_fatal_error_budget,
)
from scripts.governance.check_interface_freeze_windows import (
    evaluate_interface_freeze_windows,
)
from scripts.governance.check_evidence_package_generator_contract import (
    evaluate_evidence_package_generator_contract,
)
from scripts.governance.check_observability_redaction_tests import (
    evaluate_observability_redaction_tests,
)
from scripts.governance.check_trust_language_review import (
    evaluate_trust_language_review,
)
from scripts.governance.check_local_remote_route_policy import (
    evaluate_local_remote_route_policy,
)
from scripts.governance.check_failure_replay_harness_contract import (
    evaluate_failure_replay_harness_contract,
)
from scripts.governance.check_cold_start_truth_tests import (
    evaluate_cold_start_truth_tests,
)
from scripts.governance.check_persistence_corruption_test_suite import (
    evaluate_persistence_corruption_test_suite,
)
from scripts.governance.check_long_session_soak_tests import (
    evaluate_long_session_soak_tests,
)
from scripts.governance.check_resource_pressure_simulation_lane import (
    evaluate_resource_pressure_simulation_lane,
)
from scripts.governance.check_ui_lane_security_boundary_tests import (
    evaluate_ui_lane_security_boundary_tests,
)
from scripts.governance.check_degradation_first_ui_standard import (
    evaluate_degradation_first_ui_standard,
)
from scripts.governance.check_decision_record_operating_principles_contract import (
    evaluate_decision_record_operating_principles_contract,
)
from scripts.governance.check_naming_discipline_policy import (
    evaluate_naming_discipline_policy,
)
from scripts.governance.check_promotion_rollback_criteria import (
    evaluate_promotion_rollback_criteria,
)
from scripts.governance.check_operator_override_logging_policy import (
    evaluate_operator_override_logging_policy,
)
from scripts.governance.check_runtime_boundary_audit_checklist import evaluate_runtime_boundary_audit_checklist
from scripts.governance.check_retry_classification_policy import evaluate_retry_classification_policy
from scripts.governance.check_structured_warning_policy import evaluate_structured_warning_policy
from scripts.governance.check_unreachable_branches import (
    DEFAULT_SCAN_ROOTS as DEFAULT_UNREACHABLE_SCAN_ROOTS,
    evaluate_unreachable_branches,
)


REQUIRED_RUNTIME_CONTRACT_FILES: tuple[str, ...] = (
    "run_phase_contract.json",
    "runtime_status_vocabulary.json",
    "degradation_taxonomy.json",
    "fail_behavior_registry.json",
    "provider_truth_table.json",
    "state_transition_registry.json",
    "timeout_semantics_contract.json",
    "streaming_semantics_contract.json",
    "runtime_truth_contract_drift_report.json",
    "runtime_truth_trace_ids.json",
    "runtime_invariant_registry.json",
    "runtime_config_ownership_map.json",
    "unknown_input_policy.json",
    "clock_time_authority_policy.json",
    "capability_fallback_hierarchy.json",
    "model_profile_bios.json",
    "interrupt_semantics_policy.json",
    "idempotency_discipline_policy.json",
    "artifact_provenance_block_policy.json",
    "operator_override_logging_policy.json",
    "demo_production_labeling_policy.json",
    "human_correction_capture_policy.json",
    "sampling_discipline_guide.json",
    "execution_readiness_rubric.json",
    "release_confidence_scorecard.json",
    "feature_flag_expiration_policy.json",
    "workspace_hygiene_rules.json",
    "canonical_examples_library.json",
    "spec_debt_queue.json",
    "non_fatal_error_budget.json",
    "interface_freeze_windows.json",
    "evidence_package_generator_contract.json",
    "observability_redaction_test_contract.json",
    "trust_language_review_policy.json",
    "local_remote_route_policy.json",
    "failure_replay_harness_contract.json",
    "cold_start_truth_test_contract.json",
    "persistence_corruption_test_contract.json",
    "long_session_soak_test_contract.json",
    "resource_pressure_simulation_lane.json",
    "ui_lane_security_boundary_test_contract.json",
    "degradation_first_ui_standard.json",
    "decision_record_operating_principles_contract.json",
    "naming_discipline_policy.json",
    "promotion_rollback_criteria.json",
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run runtime truth acceptance gate checks.")
    parser.add_argument("--workspace", default=".", help="Workspace root containing observability/runs.")
    parser.add_argument("--run-id", default="", help="Optional run id for runtime contract artifact checks.")
    parser.add_argument(
        "--skip-drift-check",
        action="store_true",
        help="Skip runtime truth drift checker.",
    )
    parser.add_argument(
        "--skip-unreachable-branch-check",
        action="store_true",
        help="Skip unreachable-branch detector for critical roots.",
    )
    parser.add_argument(
        "--skip-noop-critical-path-check",
        action="store_true",
        help="Skip no-op critical-path detector for critical roots.",
    )
    parser.add_argument(
        "--skip-environment-parity-check",
        action="store_true",
        help="Skip environment parity checklist.",
    )
    parser.add_argument(
        "--skip-warning-policy-check",
        action="store_true",
        help="Skip structured warning policy contract check.",
    )
    parser.add_argument(
        "--skip-retry-policy-check",
        action="store_true",
        help="Skip retry classification policy contract check.",
    )
    parser.add_argument(
        "--skip-boundary-audit-check",
        action="store_true",
        help="Skip runtime boundary audit checklist contract check.",
    )
    parser.add_argument(
        "--skip-model-profile-bios-check",
        action="store_true",
        help="Skip model profile BIOS contract check.",
    )
    parser.add_argument(
        "--skip-interrupt-policy-check",
        action="store_true",
        help="Skip interrupt semantics policy contract check.",
    )
    parser.add_argument(
        "--skip-idempotency-policy-check",
        action="store_true",
        help="Skip idempotency discipline policy contract check.",
    )
    parser.add_argument(
        "--skip-artifact-provenance-policy-check",
        action="store_true",
        help="Skip strict artifact provenance block policy contract check.",
    )
    parser.add_argument(
        "--skip-operator-override-policy-check",
        action="store_true",
        help="Skip operator override logging policy contract check.",
    )
    parser.add_argument(
        "--skip-demo-production-policy-check",
        action="store_true",
        help="Skip demo-vs-production labeling policy contract check.",
    )
    parser.add_argument(
        "--skip-human-correction-policy-check",
        action="store_true",
        help="Skip human correction capture policy contract check.",
    )
    parser.add_argument(
        "--skip-sampling-discipline-check",
        action="store_true",
        help="Skip sampling discipline guide contract check.",
    )
    parser.add_argument(
        "--skip-execution-readiness-check",
        action="store_true",
        help="Skip execution-readiness rubric contract check.",
    )
    parser.add_argument(
        "--skip-release-confidence-check",
        action="store_true",
        help="Skip release confidence scorecard contract check.",
    )
    parser.add_argument(
        "--skip-feature-flag-expiration-check",
        action="store_true",
        help="Skip feature-flag expiration policy contract check.",
    )
    parser.add_argument(
        "--skip-workspace-hygiene-check",
        action="store_true",
        help="Skip workspace hygiene rules contract check.",
    )
    parser.add_argument(
        "--skip-canonical-examples-check",
        action="store_true",
        help="Skip canonical examples library contract check.",
    )
    parser.add_argument(
        "--skip-spec-debt-queue-check",
        action="store_true",
        help="Skip spec debt queue contract check.",
    )
    parser.add_argument(
        "--skip-non-fatal-error-budget-check",
        action="store_true",
        help="Skip non-fatal error budget contract check.",
    )
    parser.add_argument(
        "--skip-interface-freeze-windows-check",
        action="store_true",
        help="Skip interface freeze windows contract check.",
    )
    parser.add_argument(
        "--skip-evidence-package-generator-check",
        action="store_true",
        help="Skip evidence package generator contract check.",
    )
    parser.add_argument(
        "--skip-observability-redaction-tests-check",
        action="store_true",
        help="Skip observability redaction tests check.",
    )
    parser.add_argument(
        "--skip-trust-language-review-check",
        action="store_true",
        help="Skip trust language review check.",
    )
    parser.add_argument(
        "--skip-local-remote-route-policy-check",
        action="store_true",
        help="Skip local-vs-remote route policy check.",
    )
    parser.add_argument(
        "--skip-failure-replay-harness-contract-check",
        action="store_true",
        help="Skip failure replay harness contract check.",
    )
    parser.add_argument(
        "--skip-cold-start-truth-tests-check",
        action="store_true",
        help="Skip cold-start truth tests check.",
    )
    parser.add_argument(
        "--skip-persistence-corruption-tests-check",
        action="store_true",
        help="Skip persistence corruption test suite check.",
    )
    parser.add_argument(
        "--skip-long-session-soak-tests-check",
        action="store_true",
        help="Skip long-session soak tests check.",
    )
    parser.add_argument(
        "--skip-resource-pressure-simulation-lane-check",
        action="store_true",
        help="Skip resource pressure simulation lane check.",
    )
    parser.add_argument(
        "--skip-ui-lane-security-boundary-tests-check",
        action="store_true",
        help="Skip UI lane security boundary tests check.",
    )
    parser.add_argument(
        "--skip-degradation-first-ui-standard-check",
        action="store_true",
        help="Skip degradation-first UI standard check.",
    )
    parser.add_argument(
        "--skip-decision-record-operating-principles-contract-check",
        action="store_true",
        help="Skip decision-record and operating-principles contract check.",
    )
    parser.add_argument(
        "--skip-naming-discipline-policy-check",
        action="store_true",
        help="Skip naming discipline policy check.",
    )
    parser.add_argument(
        "--skip-promotion-rollback-check",
        action="store_true",
        help="Skip promotion rollback criteria contract check.",
    )
    return parser.parse_args(argv)


def _runtime_contracts_dir(workspace: Path, run_id: str) -> Path:
    return workspace / "observability" / str(run_id).strip() / "runtime_contracts"


def evaluate_runtime_truth_acceptance_gate(
    *,
    workspace: Path,
    run_id: str,
    check_drift: bool,
    check_unreachable_branches: bool = True,
    check_noop_critical_paths: bool = True,
    check_environment_parity: bool = True,
    check_warning_policy: bool = True,
    check_retry_policy: bool = True,
    check_boundary_audit: bool = True,
    check_model_profile_bios: bool = True,
    check_interrupt_policy: bool = True,
    check_idempotency_policy: bool = True,
    check_artifact_provenance_policy: bool = True,
    check_operator_override_policy: bool = True,
    check_demo_production_policy: bool = True,
    check_human_correction_policy: bool = True,
    check_sampling_discipline: bool = True,
    check_execution_readiness: bool = True,
    check_release_confidence: bool = True,
    check_feature_flag_expiration: bool = True,
    check_workspace_hygiene: bool = True,
    check_canonical_examples: bool = True,
    check_spec_debt_queue: bool = True,
    check_non_fatal_error_budget: bool = True,
    check_interface_freeze_windows: bool = True,
    check_evidence_package_generator: bool = True,
    check_observability_redaction_tests: bool = True,
    check_trust_language_review: bool = True,
    check_local_remote_route_policy: bool = True,
    check_failure_replay_harness_contract: bool = True,
    check_cold_start_truth_tests: bool = True,
    check_persistence_corruption_tests: bool = True,
    check_long_session_soak_tests: bool = True,
    check_resource_pressure_simulation_lane: bool = True,
    check_ui_lane_security_boundary_tests: bool = True,
    check_degradation_first_ui_standard: bool = True,
    check_decision_record_operating_principles_contract: bool = True,
    check_naming_discipline_policy: bool = True,
    check_promotion_rollback: bool = True,
) -> dict[str, Any]:
    failures: list[str] = []
    details: dict[str, Any] = {}

    if check_drift:
        drift = runtime_truth_contract_drift_report()
        details["drift_report"] = drift
        if not bool(drift.get("ok")):
            failures.append("runtime_truth_contract_drift")

    normalized_run_id = str(run_id or "").strip()
    if normalized_run_id:
        contracts_dir = _runtime_contracts_dir(workspace, normalized_run_id)
        missing_files: list[str] = []
        invalid_json_files: list[str] = []
        for filename in REQUIRED_RUNTIME_CONTRACT_FILES:
            path = contracts_dir / filename
            if not path.exists():
                missing_files.append(filename)
                continue
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                invalid_json_files.append(filename)
                continue
            if not isinstance(parsed, dict):
                invalid_json_files.append(filename)
        details["runtime_contracts_dir"] = str(contracts_dir)
        details["missing_files"] = missing_files
        details["invalid_json_files"] = invalid_json_files
        if missing_files:
            failures.append("runtime_contract_files_missing")
        if invalid_json_files:
            failures.append("runtime_contract_files_invalid_json")

    if check_unreachable_branches:
        roots = [workspace / path for path in DEFAULT_UNREACHABLE_SCAN_ROOTS]
        unreachable_payload = evaluate_unreachable_branches(roots=roots)
        details["unreachable_branch_check"] = {
            "ok": bool(unreachable_payload.get("ok")),
            "findings_count": len(unreachable_payload.get("findings", [])),
            "parse_errors_count": len(unreachable_payload.get("parse_errors", [])),
        }
        if not bool(unreachable_payload.get("ok")):
            failures.append("unreachable_branch_check_failed")

    if check_noop_critical_paths:
        roots = [workspace / path for path in DEFAULT_NOOP_SCAN_ROOTS]
        noop_payload = evaluate_noop_critical_paths(roots=roots)
        details["noop_critical_path_check"] = {
            "ok": bool(noop_payload.get("ok")),
            "findings_count": len(noop_payload.get("findings", [])),
            "parse_errors_count": len(noop_payload.get("parse_errors", [])),
        }
        if not bool(noop_payload.get("ok")):
            failures.append("noop_critical_path_check_failed")

    if check_environment_parity:
        parity_payload = evaluate_environment_parity_checklist(environment=None, required_keys=[])
        failed_checks = [row for row in parity_payload.get("checks", []) if not bool((row or {}).get("ok"))]
        details["environment_parity_check"] = {
            "ok": bool(parity_payload.get("ok")),
            "failed_check_count": len(failed_checks),
        }
        if not bool(parity_payload.get("ok")):
            failures.append("environment_parity_check_failed")

    if check_warning_policy:
        warning_policy_payload = evaluate_structured_warning_policy()
        details["structured_warning_policy_check"] = {
            "ok": bool(warning_policy_payload.get("ok")),
            "warning_count": int(warning_policy_payload.get("warning_count") or 0),
        }
        if not bool(warning_policy_payload.get("ok")):
            failures.append("structured_warning_policy_check_failed")

    if check_retry_policy:
        retry_policy_payload = evaluate_retry_classification_policy()
        details["retry_classification_policy_check"] = {
            "ok": bool(retry_policy_payload.get("ok")),
            "signal_count": int(retry_policy_payload.get("signal_count") or 0),
        }
        if not bool(retry_policy_payload.get("ok")):
            failures.append("retry_classification_policy_check_failed")

    if check_boundary_audit:
        boundary_payload = evaluate_runtime_boundary_audit_checklist(workspace=REPO_ROOT)
        details["runtime_boundary_audit_check"] = {
            "ok": bool(boundary_payload.get("ok")),
            "boundary_count": int(boundary_payload.get("boundary_count") or 0),
        }
        if not bool(boundary_payload.get("ok")):
            failures.append("runtime_boundary_audit_check_failed")

    if check_model_profile_bios:
        bios_payload = evaluate_model_profile_bios()
        details["model_profile_bios_check"] = {
            "ok": bool(bios_payload.get("ok")),
            "profile_count": int(bios_payload.get("profile_count") or 0),
        }
        if not bool(bios_payload.get("ok")):
            failures.append("model_profile_bios_check_failed")

    if check_interrupt_policy:
        interrupt_policy_payload = evaluate_interrupt_semantics_policy()
        details["interrupt_semantics_policy_check"] = {
            "ok": bool(interrupt_policy_payload.get("ok")),
            "surface_count": int(interrupt_policy_payload.get("surface_count") or 0),
        }
        if not bool(interrupt_policy_payload.get("ok")):
            failures.append("interrupt_semantics_policy_check_failed")

    if check_idempotency_policy:
        idempotency_policy_payload = evaluate_idempotency_discipline_policy()
        details["idempotency_discipline_policy_check"] = {
            "ok": bool(idempotency_policy_payload.get("ok")),
            "surface_count": int(idempotency_policy_payload.get("surface_count") or 0),
        }
        if not bool(idempotency_policy_payload.get("ok")):
            failures.append("idempotency_discipline_policy_check_failed")

    if check_artifact_provenance_policy:
        provenance_policy_payload = evaluate_artifact_provenance_block_policy()
        details["artifact_provenance_block_policy_check"] = {
            "ok": bool(provenance_policy_payload.get("ok")),
            "required_field_count": int(provenance_policy_payload.get("required_field_count") or 0),
        }
        if not bool(provenance_policy_payload.get("ok")):
            failures.append("artifact_provenance_block_policy_check_failed")

    if check_operator_override_policy:
        override_policy_payload = evaluate_operator_override_logging_policy()
        details["operator_override_logging_policy_check"] = {
            "ok": bool(override_policy_payload.get("ok")),
            "override_type_count": int(override_policy_payload.get("override_type_count") or 0),
        }
        if not bool(override_policy_payload.get("ok")):
            failures.append("operator_override_logging_policy_check_failed")

    if check_demo_production_policy:
        demo_policy_payload = evaluate_demo_production_labeling_policy()
        details["demo_production_labeling_policy_check"] = {
            "ok": bool(demo_policy_payload.get("ok")),
            "label_count": int(demo_policy_payload.get("label_count") or 0),
        }
        if not bool(demo_policy_payload.get("ok")):
            failures.append("demo_production_labeling_policy_check_failed")

    if check_human_correction_policy:
        correction_policy_payload = evaluate_human_correction_capture_policy()
        details["human_correction_capture_policy_check"] = {
            "ok": bool(correction_policy_payload.get("ok")),
            "target_surface_count": int(correction_policy_payload.get("target_surface_count") or 0),
        }
        if not bool(correction_policy_payload.get("ok")):
            failures.append("human_correction_capture_policy_check_failed")

    if check_sampling_discipline:
        sampling_payload = evaluate_sampling_discipline_guide()
        details["sampling_discipline_guide_check"] = {
            "ok": bool(sampling_payload.get("ok")),
            "event_class_count": int(sampling_payload.get("event_class_count") or 0),
        }
        if not bool(sampling_payload.get("ok")):
            failures.append("sampling_discipline_guide_check_failed")

    if check_execution_readiness:
        readiness_payload = evaluate_execution_readiness_rubric()
        details["execution_readiness_rubric_check"] = {
            "ok": bool(readiness_payload.get("ok")),
            "criteria_count": int(readiness_payload.get("criteria_count") or 0),
        }
        if not bool(readiness_payload.get("ok")):
            failures.append("execution_readiness_rubric_check_failed")

    if check_release_confidence:
        scorecard_payload = evaluate_release_confidence_scorecard()
        details["release_confidence_scorecard_check"] = {
            "ok": bool(scorecard_payload.get("ok")),
            "dimension_count": int(scorecard_payload.get("dimension_count") or 0),
        }
        if not bool(scorecard_payload.get("ok")):
            failures.append("release_confidence_scorecard_check_failed")

    if check_feature_flag_expiration:
        expiration_payload = evaluate_feature_flag_expiration_policy()
        details["feature_flag_expiration_policy_check"] = {
            "ok": bool(expiration_payload.get("ok")),
            "required_field_count": int(expiration_payload.get("required_field_count") or 0),
        }
        if not bool(expiration_payload.get("ok")):
            failures.append("feature_flag_expiration_policy_check_failed")

    if check_workspace_hygiene:
        workspace_hygiene_payload = evaluate_workspace_hygiene_rules()
        details["workspace_hygiene_rules_check"] = {
            "ok": bool(workspace_hygiene_payload.get("ok")),
            "rule_count": int(workspace_hygiene_payload.get("rule_count") or 0),
        }
        if not bool(workspace_hygiene_payload.get("ok")):
            failures.append("workspace_hygiene_rules_check_failed")

    if check_canonical_examples:
        examples_payload = evaluate_canonical_examples_library()
        details["canonical_examples_library_check"] = {
            "ok": bool(examples_payload.get("ok")),
            "example_count": int(examples_payload.get("example_count") or 0),
        }
        if not bool(examples_payload.get("ok")):
            failures.append("canonical_examples_library_check_failed")

    if check_spec_debt_queue:
        spec_debt_payload = evaluate_spec_debt_queue()
        details["spec_debt_queue_check"] = {
            "ok": bool(spec_debt_payload.get("ok")),
            "debt_count": int(spec_debt_payload.get("debt_count") or 0),
        }
        if not bool(spec_debt_payload.get("ok")):
            failures.append("spec_debt_queue_check_failed")

    if check_non_fatal_error_budget:
        budget_payload = evaluate_non_fatal_error_budget()
        details["non_fatal_error_budget_check"] = {
            "ok": bool(budget_payload.get("ok")),
            "budget_count": int(budget_payload.get("budget_count") or 0),
        }
        if not bool(budget_payload.get("ok")):
            failures.append("non_fatal_error_budget_check_failed")

    if check_interface_freeze_windows:
        freeze_windows_payload = evaluate_interface_freeze_windows()
        details["interface_freeze_windows_check"] = {
            "ok": bool(freeze_windows_payload.get("ok")),
            "window_count": int(freeze_windows_payload.get("window_count") or 0),
        }
        if not bool(freeze_windows_payload.get("ok")):
            failures.append("interface_freeze_windows_check_failed")

    if check_evidence_package_generator:
        evidence_contract_payload = evaluate_evidence_package_generator_contract()
        details["evidence_package_generator_contract_check"] = {
            "ok": bool(evidence_contract_payload.get("ok")),
            "required_section_count": int(evidence_contract_payload.get("required_section_count") or 0),
        }
        if not bool(evidence_contract_payload.get("ok")):
            failures.append("evidence_package_generator_contract_check_failed")

    if check_observability_redaction_tests:
        redaction_tests_payload = evaluate_observability_redaction_tests()
        details["observability_redaction_tests_check"] = {
            "ok": bool(redaction_tests_payload.get("ok")),
            "check_count": int(redaction_tests_payload.get("check_count") or 0),
        }
        if not bool(redaction_tests_payload.get("ok")):
            failures.append("observability_redaction_tests_check_failed")

    if check_trust_language_review:
        trust_language_payload = evaluate_trust_language_review()
        details["trust_language_review_check"] = {
            "ok": bool(trust_language_payload.get("ok")),
            "claim_count": int(trust_language_payload.get("claim_count") or 0),
        }
        if not bool(trust_language_payload.get("ok")):
            failures.append("trust_language_review_check_failed")

    if check_local_remote_route_policy:
        local_remote_route_payload = evaluate_local_remote_route_policy()
        details["local_remote_route_policy_check"] = {
            "ok": bool(local_remote_route_payload.get("ok")),
            "lane_count": int(local_remote_route_payload.get("lane_count") or 0),
        }
        if not bool(local_remote_route_payload.get("ok")):
            failures.append("local_remote_route_policy_check_failed")

    if check_failure_replay_harness_contract:
        replay_harness_contract_payload = evaluate_failure_replay_harness_contract()
        details["failure_replay_harness_contract_check"] = {
            "ok": bool(replay_harness_contract_payload.get("ok")),
            "required_output_field_count": int(replay_harness_contract_payload.get("required_output_field_count") or 0),
        }
        if not bool(replay_harness_contract_payload.get("ok")):
            failures.append("failure_replay_harness_contract_check_failed")

    if check_cold_start_truth_tests:
        cold_start_truth_payload = evaluate_cold_start_truth_tests()
        details["cold_start_truth_tests_check"] = {
            "ok": bool(cold_start_truth_payload.get("ok")),
            "check_count": int(cold_start_truth_payload.get("check_count") or 0),
        }
        if not bool(cold_start_truth_payload.get("ok")):
            failures.append("cold_start_truth_tests_check_failed")

    if check_persistence_corruption_tests:
        persistence_corruption_payload = evaluate_persistence_corruption_test_suite()
        details["persistence_corruption_tests_check"] = {
            "ok": bool(persistence_corruption_payload.get("ok")),
            "check_count": int(persistence_corruption_payload.get("check_count") or 0),
        }
        if not bool(persistence_corruption_payload.get("ok")):
            failures.append("persistence_corruption_tests_check_failed")

    if check_long_session_soak_tests:
        long_session_soak_payload = evaluate_long_session_soak_tests()
        details["long_session_soak_tests_check"] = {
            "ok": bool(long_session_soak_payload.get("ok")),
            "check_count": int(long_session_soak_payload.get("check_count") or 0),
            "turn_count": int(long_session_soak_payload.get("turn_count") or 0),
        }
        if not bool(long_session_soak_payload.get("ok")):
            failures.append("long_session_soak_tests_check_failed")

    if check_resource_pressure_simulation_lane:
        pressure_lane_payload = evaluate_resource_pressure_simulation_lane()
        details["resource_pressure_simulation_lane_check"] = {
            "ok": bool(pressure_lane_payload.get("ok")),
            "check_count": int(pressure_lane_payload.get("check_count") or 0),
        }
        if not bool(pressure_lane_payload.get("ok")):
            failures.append("resource_pressure_simulation_lane_check_failed")

    if check_ui_lane_security_boundary_tests:
        ui_lane_boundary_payload = evaluate_ui_lane_security_boundary_tests()
        details["ui_lane_security_boundary_tests_check"] = {
            "ok": bool(ui_lane_boundary_payload.get("ok")),
            "check_count": int(ui_lane_boundary_payload.get("check_count") or 0),
        }
        if not bool(ui_lane_boundary_payload.get("ok")):
            failures.append("ui_lane_security_boundary_tests_check_failed")

    if check_degradation_first_ui_standard:
        degradation_first_payload = evaluate_degradation_first_ui_standard()
        details["degradation_first_ui_standard_check"] = {
            "ok": bool(degradation_first_payload.get("ok")),
            "check_count": int(degradation_first_payload.get("check_count") or 0),
        }
        if not bool(degradation_first_payload.get("ok")):
            failures.append("degradation_first_ui_standard_check_failed")

    if check_decision_record_operating_principles_contract:
        decision_record_payload = evaluate_decision_record_operating_principles_contract(workspace=REPO_ROOT)
        details["decision_record_operating_principles_contract_check"] = {
            "ok": bool(decision_record_payload.get("ok")),
            "check_count": int(decision_record_payload.get("check_count") or 0),
        }
        if not bool(decision_record_payload.get("ok")):
            failures.append("decision_record_operating_principles_contract_check_failed")

    if check_naming_discipline_policy:
        naming_policy_payload = evaluate_naming_discipline_policy()
        details["naming_discipline_policy_check"] = {
            "ok": bool(naming_policy_payload.get("ok")),
            "convention_count": int(naming_policy_payload.get("convention_count") or 0),
        }
        if not bool(naming_policy_payload.get("ok")):
            failures.append("naming_discipline_policy_check_failed")

    if check_promotion_rollback:
        rollback_payload = evaluate_promotion_rollback_criteria()
        details["promotion_rollback_criteria_check"] = {
            "ok": bool(rollback_payload.get("ok")),
            "trigger_count": int(rollback_payload.get("trigger_count") or 0),
        }
        if not bool(rollback_payload.get("ok")):
            failures.append("promotion_rollback_criteria_check_failed")

    return {
        "schema_version": "runtime_truth_acceptance_gate.v1",
        "ok": not failures,
        "failures": failures,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=Path(args.workspace).resolve(),
        run_id=str(args.run_id or "").strip(),
        check_drift=not bool(args.skip_drift_check),
        check_unreachable_branches=not bool(args.skip_unreachable_branch_check),
        check_noop_critical_paths=not bool(args.skip_noop_critical_path_check),
        check_environment_parity=not bool(args.skip_environment_parity_check),
        check_warning_policy=not bool(args.skip_warning_policy_check),
        check_retry_policy=not bool(args.skip_retry_policy_check),
        check_boundary_audit=not bool(args.skip_boundary_audit_check),
        check_model_profile_bios=not bool(args.skip_model_profile_bios_check),
        check_interrupt_policy=not bool(args.skip_interrupt_policy_check),
        check_idempotency_policy=not bool(args.skip_idempotency_policy_check),
        check_artifact_provenance_policy=not bool(args.skip_artifact_provenance_policy_check),
        check_operator_override_policy=not bool(args.skip_operator_override_policy_check),
        check_demo_production_policy=not bool(args.skip_demo_production_policy_check),
        check_human_correction_policy=not bool(args.skip_human_correction_policy_check),
        check_sampling_discipline=not bool(args.skip_sampling_discipline_check),
        check_execution_readiness=not bool(args.skip_execution_readiness_check),
        check_release_confidence=not bool(args.skip_release_confidence_check),
        check_feature_flag_expiration=not bool(args.skip_feature_flag_expiration_check),
        check_workspace_hygiene=not bool(args.skip_workspace_hygiene_check),
        check_canonical_examples=not bool(args.skip_canonical_examples_check),
        check_spec_debt_queue=not bool(args.skip_spec_debt_queue_check),
        check_non_fatal_error_budget=not bool(args.skip_non_fatal_error_budget_check),
        check_interface_freeze_windows=not bool(args.skip_interface_freeze_windows_check),
        check_evidence_package_generator=not bool(args.skip_evidence_package_generator_check),
        check_observability_redaction_tests=not bool(args.skip_observability_redaction_tests_check),
        check_trust_language_review=not bool(args.skip_trust_language_review_check),
        check_local_remote_route_policy=not bool(args.skip_local_remote_route_policy_check),
        check_failure_replay_harness_contract=not bool(args.skip_failure_replay_harness_contract_check),
        check_cold_start_truth_tests=not bool(args.skip_cold_start_truth_tests_check),
        check_persistence_corruption_tests=not bool(args.skip_persistence_corruption_tests_check),
        check_long_session_soak_tests=not bool(args.skip_long_session_soak_tests_check),
        check_resource_pressure_simulation_lane=not bool(args.skip_resource_pressure_simulation_lane_check),
        check_ui_lane_security_boundary_tests=not bool(args.skip_ui_lane_security_boundary_tests_check),
        check_degradation_first_ui_standard=not bool(args.skip_degradation_first_ui_standard_check),
        check_decision_record_operating_principles_contract=not bool(
            args.skip_decision_record_operating_principles_contract_check
        ),
        check_naming_discipline_policy=not bool(args.skip_naming_discipline_policy_check),
        check_promotion_rollback=not bool(args.skip_promotion_rollback_check),
    )
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
