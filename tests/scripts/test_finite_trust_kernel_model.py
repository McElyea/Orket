from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.finite_trust_kernel_model import (
    FINITE_TRUST_KERNEL_MODEL_SCHEMA_VERSION,
    MODEL_SIGNATURE_ROLE,
    evaluate_finite_trust_kernel_model,
)
from scripts.proof.offline_trusted_run_verifier import TARGET_CLAIM_TIER
from scripts.proof.trusted_repo_change_contract import DEFAULT_BUNDLE_NAME, FALLBACK_CLAIM_TIER
from scripts.proof.trusted_repo_change_verifier import build_trusted_repo_change_campaign_report
from scripts.proof.trusted_repo_change_workflow import execute_trusted_repo_change
from scripts.proof.trusted_run_non_interference import evaluate_offline_verifier_non_interference


def test_finite_model_accepts_repo_change_campaign(tmp_path: Path) -> None:
    """Layer: contract. Verifies the finite model accepts the admitted repo-change campaign evidence."""
    campaign = _campaign(tmp_path / "workspace-a")

    model = evaluate_finite_trust_kernel_model(campaign, requested_claims=[TARGET_CLAIM_TIER])

    assert model["schema_version"] == FINITE_TRUST_KERNEL_MODEL_SCHEMA_VERSION
    assert model["model_result"] == "accepted"
    assert model["observed_path"] == "primary"
    assert model["observed_result"] == "success"
    assert model["claim_status"] == "allowed"
    assert model["claim_tier"] == TARGET_CLAIM_TIER
    assert model["signature_role"] == MODEL_SIGNATURE_ROLE
    assert model["missing_evidence"] == []
    assert model["model_signature_digest"].startswith("sha256:")
    assert _state(model, "verifier_accepted") == "observed"


def test_finite_model_signature_is_stable_for_equivalent_campaigns(tmp_path: Path) -> None:
    """Layer: contract. Verifies canonical normalization ignores run-local identifiers and timestamps."""
    first = evaluate_finite_trust_kernel_model(_campaign(tmp_path / "workspace-a"), requested_claims=[TARGET_CLAIM_TIER])
    second = evaluate_finite_trust_kernel_model(_campaign(tmp_path / "workspace-b"), requested_claims=[TARGET_CLAIM_TIER])

    assert first["model_signature_digest"] == second["model_signature_digest"]
    assert "run_id" in first["canonical_normalization"]["non_semantic_exclusions"]
    assert "recorded_at_utc" in first["canonical_normalization"]["non_semantic_exclusions"]


def test_finite_model_rejects_missing_final_truth(tmp_path: Path) -> None:
    """Layer: contract. Verifies success-shaped evidence cannot omit final truth."""
    bundle = _bundle(tmp_path / "workspace")
    bundle["authority_lineage"].pop("final_truth")

    model = evaluate_finite_trust_kernel_model(bundle, requested_claims=[FALLBACK_CLAIM_TIER])

    assert model["model_result"] == "rejected"
    assert "missing_final_truth" in model["missing_evidence"]
    assert _cause(model, "missing_final_truth") == "missing_evidence"
    assert _forbidden_status(model, "success_without_final_truth") == "blocked"


def test_finite_model_rejects_validator_failure_as_contradictory_evidence(tmp_path: Path) -> None:
    """Layer: contract. Verifies failing validator evidence blocks success final truth."""
    live = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="validator_failure")

    model = evaluate_finite_trust_kernel_model(live["witness_report"], requested_claims=[FALLBACK_CLAIM_TIER])

    assert model["model_result"] == "rejected"
    assert "validator_failed" in model["missing_evidence"]
    assert _cause(model, "validator_failed") == "contradictory_evidence"


def test_finite_model_reports_downgrade_for_replay_overclaim(tmp_path: Path) -> None:
    """Layer: contract. Verifies unsupported higher claims downgrade instead of replacing authority."""
    campaign = _campaign(tmp_path / "workspace")

    model = evaluate_finite_trust_kernel_model(campaign, requested_claims=["replay_deterministic"])

    assert model["model_result"] == "downgraded"
    assert model["observed_path"] == "degraded"
    assert model["observed_result"] == "partial success"
    assert model["claim_tier"] == TARGET_CLAIM_TIER
    assert model["claim_downgrade_reasons"] == ["replay_evidence_missing"]
    assert _cause(model, "replay_evidence_missing") == "unsupported_claim_request"
    assert _state(model, "claim_downgraded") == "observed"


def test_finite_model_classifies_compare_scope_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies compare-scope drift is rejected as contradictory evidence."""
    campaign = _campaign(tmp_path / "workspace")
    campaign["compare_scope"] = "other_scope"

    model = evaluate_finite_trust_kernel_model(campaign, requested_claims=[TARGET_CLAIM_TIER])

    assert model["model_result"] == "rejected"
    assert "compare_scope_mismatch" in model["missing_evidence"]
    assert _cause(model, "compare_scope_mismatch") == "contradictory_evidence"


def test_finite_model_classifies_malformed_input() -> None:
    """Layer: contract. Verifies unsupported serialized evidence fails closed with a malformed cause."""
    model = evaluate_finite_trust_kernel_model({"schema_version": "unknown"})

    assert model["model_result"] == "rejected"
    assert "schema_version_missing_or_unsupported" in model["missing_evidence"]
    assert _cause(model, "schema_version_missing_or_unsupported") == "malformed_evidence"
    assert _state(model, "no_admissible_bundle") == "observed"


def test_finite_model_module_is_side_effect_free_by_structural_inspection() -> None:
    """Layer: structural. Verifies the finite-model module has no forbidden verifier side-effect surface."""
    report = evaluate_offline_verifier_non_interference(
        module_paths=[
            "scripts/proof/finite_trust_kernel_model.py",
            "scripts/proof/verify_offline_trusted_run_claim.py",
        ],
        use_cache=False,
    )

    assert report["result"] == "pass"
    assert report["forbidden_import_hits"] == []
    assert report["forbidden_call_hits"] == []


def _campaign(workspace: Path) -> dict[str, object]:
    first = execute_trusted_repo_change(workspace_root=workspace, scenario="approved", run_index=1)
    second = execute_trusted_repo_change(workspace_root=workspace, scenario="approved", run_index=2)
    return build_trusted_repo_change_campaign_report([first["witness_report"], second["witness_report"]])


def _bundle(workspace: Path) -> dict[str, object]:
    live = execute_trusted_repo_change(workspace_root=workspace, scenario="approved")
    bundle_path = workspace / "runs" / str(live["session_id"]) / DEFAULT_BUNDLE_NAME
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _state(model: dict[str, object], state: str) -> str:
    for item in model.get("states") or []:
        if item.get("state") == state:
            return str(item.get("status") or "")
    return ""


def _cause(model: dict[str, object], reason_code: str) -> str:
    for item in model.get("failure_causes") or []:
        if item.get("reason_code") == reason_code:
            return str(item.get("cause") or "")
    return ""


def _forbidden_status(model: dict[str, object], transition: str) -> str:
    for item in model.get("forbidden_transition_results") or []:
        if item.get("forbidden_transition") == transition:
            return str(item.get("status") or "")
    return ""
