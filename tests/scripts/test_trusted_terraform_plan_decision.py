from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.proof.offline_trusted_run_verifier import TARGET_CLAIM_TIER
from scripts.proof.run_trusted_terraform_plan_decision import main as run_trusted_terraform_plan_decision_main
from scripts.proof.run_trusted_terraform_plan_decision_campaign import main as run_trusted_terraform_plan_decision_campaign_main
from scripts.proof.trusted_terraform_plan_decision_contract import (
    DEFAULT_BUNDLE_NAME,
    build_contract_verdict,
)
from scripts.proof.trusted_terraform_plan_decision_offline import evaluate_trusted_terraform_plan_decision_offline_claim
from scripts.proof.trusted_terraform_plan_decision_verifier import (
    build_trusted_terraform_plan_decision_campaign_report,
    verify_trusted_terraform_plan_decision_bundle_payload,
)
from scripts.proof.trusted_terraform_plan_decision_workflow import execute_trusted_terraform_plan_decision
from scripts.proof.verify_offline_trusted_run_claim import main as offline_verifier_main


def test_risky_publish_workflow_emits_valid_witness_bundle(tmp_path: Path) -> None:
    """Layer: integration. Verifies the Terraform trusted-scope wrapper emits a valid success-shaped witness bundle."""
    live = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish")
    bundle = _bundle_from_live(tmp_path / "workspace", live)

    assert live["observed_result"] == "success"
    assert live["publish_decision"] == "normal_publish"
    assert live["risk_verdict"] == "risky_for_v1_policy"
    assert bundle["contract_verdict"]["verdict"] == "pass"
    assert verify_trusted_terraform_plan_decision_bundle_payload(bundle)["observed_result"] == "success"


def test_degraded_publish_preserves_trusted_decision_truth(tmp_path: Path) -> None:
    """Layer: integration. Verifies summarizer failure degrades publication without breaking trusted decision proof."""
    live = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="degraded_publish")
    bundle = _bundle_from_live(tmp_path / "workspace", live)

    assert live["observed_result"] == "success"
    assert live["execution_status"] == "degraded"
    assert live["publish_decision"] == "degraded_publish"
    assert live["summary_status"] == "summary_unavailable"
    assert bundle["validator_result"]["validation_result"] == "pass"
    assert verify_trusted_terraform_plan_decision_bundle_payload(bundle)["observed_result"] == "success"


@pytest.mark.parametrize(
    ("scenario", "expected_status"),
    [("no_publish_invalid_json", "failure"), ("blocked_capability", "blocked_by_policy")],
)
def test_negative_workflow_scenarios_fail_truthfully(tmp_path: Path, scenario: str, expected_status: str) -> None:
    """Layer: integration. Verifies non-success Terraform review outcomes stay non-promotable but still evidence-backed."""
    live = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario=scenario)

    assert live["observed_result"] == "success"
    assert live["execution_status"] == expected_status
    assert live["publish_decision"] == "no_publish"
    assert live["witness_report"]["observed_result"] == "failure"


def test_campaign_and_offline_verifier_allow_verdict_deterministic(tmp_path: Path) -> None:
    """Layer: contract. Verifies repeat Terraform decision evidence reaches only the bounded verdict claim tier."""
    first = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish", run_index=1)
    second = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish", run_index=2)
    campaign = build_trusted_terraform_plan_decision_campaign_report([first["witness_report"], second["witness_report"]])

    report = evaluate_trusted_terraform_plan_decision_offline_claim(campaign, requested_claims=[TARGET_CLAIM_TIER])

    assert campaign["observed_result"] == "success"
    assert campaign["claim_tier"] == TARGET_CLAIM_TIER
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == TARGET_CLAIM_TIER


@pytest.mark.parametrize(
    ("corruption_id", "mutate", "expected"),
    [
        ("TTPD-CORR-001", lambda item: item["validator_result"].__setitem__("missing_evidence", ["invalid_json_plan_input"]), "invalid_json_plan_input"),
        ("TTPD-CORR-002", lambda item: item["validator_result"].__setitem__("missing_evidence", ["forbidden_operation_hits_drift"]), "forbidden_operation_hits_drift"),
        ("TTPD-CORR-003", lambda item: item["validator_result"].__setitem__("missing_evidence", ["risk_verdict_drift"]), "risk_verdict_drift"),
        ("TTPD-CORR-004", lambda item: item["observed_effect"].__setitem__("deterministic_analysis_complete", False), "publish_without_complete_analysis"),
        ("TTPD-CORR-005", lambda item: item["authority_lineage"].pop("audit_publication"), "audit_publication_without_publish"),
        ("TTPD-CORR-006", lambda item: item["observed_effect"].__setitem__("forbidden_mutations", ["workspace/rogue.json"]), "undeclared_durable_mutation"),
        ("TTPD-CORR-007", lambda item: item.__setitem__("compare_scope", "other"), "compare_scope_missing_or_unsupported"),
        ("TTPD-CORR-008", lambda item: item.__setitem__("operator_surface", "other"), "operator_surface_missing"),
        ("TTPD-CORR-009", lambda item: item["authority_lineage"].pop("final_truth"), "missing_final_truth"),
    ],
)
def test_corruption_matrix_fails_closed(tmp_path: Path, corruption_id: str, mutate: object, expected: str) -> None:
    """Layer: contract. Verifies the Terraform compare scope catches its admitted corruption set."""
    live = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish")
    bundle = _bundle_from_live(tmp_path / "workspace", live)

    mutate(bundle)
    bundle["contract_verdict"] = build_contract_verdict(copy.deepcopy(bundle))
    report = verify_trusted_terraform_plan_decision_bundle_payload(bundle)

    assert report["observed_result"] == "failure", corruption_id
    assert expected in report["missing_evidence"], corruption_id


def test_replay_and_text_overclaims_downgrade(tmp_path: Path) -> None:
    """Layer: contract. Verifies unsupported Terraform higher claims remain forbidden."""
    first = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish", run_index=1)
    second = execute_trusted_terraform_plan_decision(workspace_root=tmp_path / "workspace", scenario="risky_publish", run_index=2)
    campaign = build_trusted_terraform_plan_decision_campaign_report([first["witness_report"], second["witness_report"]])

    replay = evaluate_trusted_terraform_plan_decision_offline_claim(campaign, requested_claims=["replay_deterministic"])
    text = evaluate_trusted_terraform_plan_decision_offline_claim(campaign, requested_claims=["text_deterministic"])

    assert replay["claim_status"] == "downgraded"
    assert replay["claim_tier"] == TARGET_CLAIM_TIER
    assert _forbidden_reasons(replay, "replay_deterministic") == ["replay_evidence_missing"]
    assert text["claim_status"] == "downgraded"
    assert text["claim_tier"] == TARGET_CLAIM_TIER
    assert _forbidden_reasons(text, "text_deterministic") == ["text_identity_evidence_missing"]


def test_cli_commands_write_diff_ledger_outputs(tmp_path: Path) -> None:
    """Layer: integration. Verifies the Terraform proof CLIs write stable diff-ledger JSON outputs."""
    live_output = tmp_path / "live.json"
    campaign_output = tmp_path / "campaign.json"
    offline_output = tmp_path / "offline.json"
    workspace = tmp_path / "workspace"

    live_exit = run_trusted_terraform_plan_decision_main(["--workspace-root", str(workspace), "--output", str(live_output)])
    campaign_exit = run_trusted_terraform_plan_decision_campaign_main(["--workspace-root", str(workspace), "--output", str(campaign_output)])
    offline_exit = offline_verifier_main(["--input", str(campaign_output), "--output", str(offline_output), "--claim", TARGET_CLAIM_TIER])

    assert live_exit == 0
    assert campaign_exit == 0
    assert offline_exit == 0
    assert isinstance(json.loads(live_output.read_text(encoding="utf-8")).get("diff_ledger"), list)
    assert isinstance(json.loads(campaign_output.read_text(encoding="utf-8")).get("diff_ledger"), list)
    assert json.loads(offline_output.read_text(encoding="utf-8"))["claim_tier"] == TARGET_CLAIM_TIER


def _bundle_from_live(workspace: Path, live: dict[str, object]) -> dict[str, object]:
    bundle_path = workspace / "runs" / str(live["session_id"]) / DEFAULT_BUNDLE_NAME
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _forbidden_reasons(report: dict[str, object], claim_tier: str) -> list[str]:
    for item in report.get("forbidden_claims") or []:
        if item.get("claim_tier") == claim_tier:
            return list(item.get("reason_codes") or [])
    return []
