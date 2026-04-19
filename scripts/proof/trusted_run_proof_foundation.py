from __future__ import annotations

import copy
from typing import Any, Callable

from scripts.proof.trusted_run_witness_contract import (
    COMPARE_SCOPE,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    now_utc_iso,
    stable_json_digest,
)
from scripts.proof.trusted_run_non_interference import evaluate_offline_verifier_non_interference
from scripts.proof.trusted_run_witness_fixture_bundle import build_valid_trusted_run_witness_bundle

PROOF_FOUNDATION_SCHEMA_VERSION = "trusted_run_proof_foundation.v1"
DEFAULT_PROOF_FOUNDATION_OUTPUT = PROOF_RESULTS_ROOT / "trusted_run_proof_foundation.json"


def build_trusted_run_proof_foundation_report() -> dict[str, Any]:
    from scripts.proof.offline_trusted_run_verifier import evaluate_offline_trusted_run_claim
    from scripts.proof.trusted_run_invariant_model import evaluate_trusted_run_invariants
    from scripts.proof.trusted_run_witness_contract import verify_witness_bundle_payload

    base_bundle = build_valid_trusted_run_witness_bundle()
    base_invariant = evaluate_trusted_run_invariants(base_bundle)
    base_report = verify_witness_bundle_payload(base_bundle, evidence_ref="runs/sess-a/trusted_run_witness_bundle.json")
    non_interference = evaluate_offline_verifier_non_interference()
    targets = [
        _build_invariant_target(
            target="step_lineage_missing_or_drifted",
            source_surface="docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
            mutate=_break_step_lineage,
            expected_failure="step_lineage_missing_or_drifted",
            base_invariant=base_invariant,
        ),
        _build_invariant_target(
            target="lease_source_reservation_not_verified",
            source_surface="docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
            mutate=_break_reservation_trace,
            expected_failure="lease_source_reservation_not_verified",
            base_invariant=base_invariant,
        ),
        _build_invariant_target(
            target="resource_lease_consistency_not_verified",
            source_surface="docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
            mutate=_break_resource_lease_consistency,
            expected_failure="resource_lease_consistency_not_verified",
            base_invariant=base_invariant,
        ),
        _build_invariant_target(
            target="effect_prior_chain_not_verified",
            source_surface="docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
            mutate=_break_effect_prior_chain,
            expected_failure="effect_prior_chain_not_verified",
            base_invariant=base_invariant,
        ),
        _build_invariant_target(
            target="final_truth_cardinality_not_verified",
            source_surface="docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md",
            mutate=_break_final_truth_cardinality,
            expected_failure="final_truth_cardinality_not_verified",
            base_invariant=base_invariant,
        ),
        _build_non_interference_target(
            non_interference=non_interference,
            base_report=base_report,
            offline_claim=evaluate_offline_trusted_run_claim,
        ),
    ]
    result = "success" if all(item["status"] == "pass" for item in targets) else "failure"
    report = {
        "schema_version": PROOF_FOUNDATION_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": result,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "foundation_targets": targets,
        "base_bundle_result": {
            "invariant_result": base_invariant.get("result"),
            "verifier_result": base_report.get("observed_result"),
            "invariant_signature_digest": str(base_invariant.get("invariant_signature_digest") or ""),
            "substrate_signature_digest": str(base_report.get("substrate_signature_digest") or ""),
        },
        "non_interference": non_interference,
        "limitations": [
            "structural proof over the canonical fixture bundle and current verifier source files",
            "does not broaden public trust wording or claim replay/text determinism",
        ],
    }
    report["report_signature_digest"] = stable_json_digest(_foundation_signature_material(report))
    return report


def _build_invariant_target(
    *,
    target: str,
    source_surface: str,
    mutate: Callable[[dict[str, Any]], None],
    expected_failure: str,
    base_invariant: dict[str, Any],
) -> dict[str, Any]:
    from scripts.proof.trusted_run_invariant_model import evaluate_trusted_run_invariants
    from scripts.proof.trusted_run_witness_contract import verify_witness_bundle_payload

    corrupted = build_valid_trusted_run_witness_bundle()
    mutate(corrupted)
    negative_invariant = evaluate_trusted_run_invariants(corrupted)
    negative_report = verify_witness_bundle_payload(corrupted)
    positive_ok = base_invariant.get("result") == "pass" and expected_failure not in list(base_invariant.get("failures") or [])
    negative_ok = (
        expected_failure in list(negative_invariant.get("failures") or [])
        and expected_failure in list(negative_report.get("missing_evidence") or [])
    )
    status = "pass" if positive_ok and negative_ok else "fail"
    return {
        "target": target,
        "source_surface": source_surface,
        "status": status,
        "positive_case": {
            "status": "pass" if positive_ok else "fail",
            "invariant_result": base_invariant.get("result"),
        },
        "negative_case": {
            "status": "pass" if negative_ok else "fail",
            "expected_failure": expected_failure,
            "observed_invariant_failures": list(negative_invariant.get("failures") or []),
            "observed_verifier_failures": list(negative_report.get("missing_evidence") or []),
        },
    }


def _build_non_interference_target(
    *,
    non_interference: dict[str, Any],
    base_report: dict[str, Any],
    offline_claim: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    degraded_report = copy.deepcopy(base_report)
    degraded_report.pop("side_effect_free_verification", None)
    negative_report = offline_claim(degraded_report, input_mode="single_report")
    negative_ok = "verifier_side_effect_absence_not_mechanically_proven" in list(negative_report.get("missing_evidence") or [])
    positive_ok = non_interference.get("result") == "pass"
    status = "pass" if positive_ok and negative_ok else "fail"
    return {
        "target": "verifier_side_effect_absence_not_mechanically_proven",
        "source_surface": "docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md",
        "status": status,
        "positive_case": {
            "status": "pass" if positive_ok else "fail",
            "non_interference_signature_digest": str(non_interference.get("non_interference_signature_digest") or ""),
            "checked_files": [item["relative_path"] for item in non_interference.get("inspected_files") or []],
        },
        "negative_case": {
            "status": "pass" if negative_ok else "fail",
            "expected_failure": "verifier_side_effect_absence_not_mechanically_proven",
            "observed_missing_evidence": list(negative_report.get("missing_evidence") or []),
            "observed_claim_status": str(negative_report.get("claim_status") or ""),
        },
    }


def _break_step_lineage(bundle: dict[str, Any]) -> None:
    bundle["authority_lineage"]["step"]["latest_step_id"] = "orphan-step"


def _break_reservation_trace(bundle: dict[str, Any]) -> None:
    bundle["authority_lineage"].pop("reservation", None)


def _break_resource_lease_consistency(bundle: dict[str, Any]) -> None:
    bundle["authority_lineage"]["resource"]["provenance_ref"] = "turn-tool-lease:other-run"


def _break_effect_prior_chain(bundle: dict[str, Any]) -> None:
    bundle["authority_lineage"]["effect_journal"].pop("latest_prior_entry_digest", None)


def _break_final_truth_cardinality(bundle: dict[str, Any]) -> None:
    bundle["authority_lineage"]["run"]["final_truth_record_id"] = "turn-tool-final-truth:other"


def _foundation_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": PROOF_FOUNDATION_SCHEMA_VERSION,
        "compare_scope": report.get("compare_scope"),
        "operator_surface": report.get("operator_surface"),
        "observed_result": report.get("observed_result"),
        "targets": {item["target"]: item["status"] for item in report.get("foundation_targets") or []},
        "non_interference_signature_digest": _safe_non_interference_digest(report),
    }


def _safe_non_interference_digest(report: dict[str, Any]) -> str:
    non_interference = report.get("non_interference")
    return str(non_interference.get("non_interference_signature_digest") or "") if isinstance(non_interference, dict) else ""
