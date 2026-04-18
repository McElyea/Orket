from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.proof.offline_trusted_run_verifier import TARGET_CLAIM_TIER
from scripts.proof.run_trusted_repo_change import main as run_trusted_repo_change_main
from scripts.proof.run_trusted_repo_change_campaign import main as run_trusted_repo_change_campaign_main
from scripts.proof.trusted_repo_change_contract import (
    CONFIG_ARTIFACT_PATH,
    DEFAULT_BUNDLE_NAME,
    EXPECTED_CONFIG,
    VALIDATOR_SCHEMA_VERSION,
    build_contract_verdict,
    expected_config_payload,
    validate_config_artifact,
)
from scripts.proof.trusted_repo_change_offline import evaluate_trusted_repo_change_offline_claim
from scripts.proof.trusted_repo_change_verifier import (
    build_trusted_repo_change_campaign_report,
    verify_trusted_repo_change_bundle_payload,
)
from scripts.proof.trusted_repo_change_workflow import execute_trusted_repo_change
from scripts.proof.verify_offline_trusted_run_claim import main as offline_verifier_main


def test_validator_accepts_expected_config(tmp_path: Path) -> None:
    """Layer: unit. Verifies the deterministic validator accepts only the expected config contract."""
    config_path = tmp_path / CONFIG_ARTIFACT_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(expected_config_payload()), encoding="utf-8")

    report = validate_config_artifact(config_path)

    assert report["schema_version"] == VALIDATOR_SCHEMA_VERSION
    assert report["validation_result"] == "pass"
    assert report["missing_evidence"] == []
    assert report["validator_signature_digest"].startswith("sha256:")


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda payload: payload.__setitem__("schema_version", "wrong"), "wrong_config_schema"),
        (lambda payload: payload.__setitem__("risk_class", "high"), "wrong_config_content"),
        (lambda payload: payload.__setitem__("extra", True), "wrong_config_content"),
    ],
)
def test_validator_rejects_wrong_schema_content_and_extra_properties(tmp_path: Path, mutate: object, expected: str) -> None:
    """Layer: unit. Verifies config validation fails closed with machine-readable reasons."""
    payload = expected_config_payload()
    mutate(payload)
    config_path = tmp_path / CONFIG_ARTIFACT_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_config_artifact(config_path)

    assert report["validation_result"] == "fail"
    assert expected in report["missing_evidence"]


def test_approved_workflow_emits_valid_witness_bundle(tmp_path: Path) -> None:
    """Layer: integration. Verifies the approved fixture change writes, validates, and witnesses successfully."""
    live = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved")
    bundle = _bundle_from_live(tmp_path / "workspace", live)

    assert live["observed_result"] == "success"
    assert live["workflow_result"] == "success"
    assert json.loads((tmp_path / "workspace" / CONFIG_ARTIFACT_PATH).read_text(encoding="utf-8")) == EXPECTED_CONFIG
    assert bundle["contract_verdict"]["verdict"] == "pass"
    assert verify_trusted_repo_change_bundle_payload(bundle)["observed_result"] == "success"


def test_denial_terminal_stops_without_mutation(tmp_path: Path) -> None:
    """Layer: integration. Verifies denial is a terminal non-success workflow result without file mutation."""
    live = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="denied")

    assert live["observed_result"] == "success"
    assert live["workflow_result"] == "blocked"
    assert live["artifact_changed"] is False
    assert not (tmp_path / "workspace" / CONFIG_ARTIFACT_PATH).exists()
    assert live["witness_bundle_ref"] == ""


def test_validator_failure_blocks_successful_final_truth(tmp_path: Path) -> None:
    """Layer: integration. Verifies invalid config cannot reach successful final truth."""
    live = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="validator_failure")

    assert live["observed_result"] == "success"
    assert live["workflow_result"] == "failure"
    assert live["validator_result"]["validation_result"] == "fail"
    assert live["witness_report"]["observed_result"] == "failure"
    assert "validator_failed" in live["witness_report"]["missing_evidence"]


def test_campaign_and_offline_verifier_allow_verdict_deterministic(tmp_path: Path) -> None:
    """Layer: contract. Verifies repeat evidence promotes only the bounded verdict claim."""
    first = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved", run_index=1)
    second = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved", run_index=2)
    campaign = build_trusted_repo_change_campaign_report([first["witness_report"], second["witness_report"]])

    report = evaluate_trusted_repo_change_offline_claim(campaign, requested_claims=[TARGET_CLAIM_TIER])

    assert campaign["observed_result"] == "success"
    assert campaign["claim_tier"] == TARGET_CLAIM_TIER
    assert report["claim_status"] == "allowed"
    assert report["claim_tier"] == TARGET_CLAIM_TIER


@pytest.mark.parametrize(
    ("corruption_id", "mutate", "expected"),
    [
        ("FUWS-CORR-001", lambda item: item["validator_result"].__setitem__("missing_evidence", ["wrong_config_schema"]), "wrong_config_schema"),
        ("FUWS-CORR-002", lambda item: item["authority_lineage"].pop("operator_action"), "missing_approval_resolution"),
        ("FUWS-CORR-003", lambda item: item["authority_lineage"].pop("checkpoint"), "checkpoint_missing_or_drifted"),
        ("FUWS-CORR-004", lambda item: item["authority_lineage"].pop("reservation"), "resource_or_lease_evidence_missing"),
        ("FUWS-CORR-005", lambda item: item["authority_lineage"].pop("effect_journal"), "missing_effect_evidence"),
        ("FUWS-CORR-006", lambda item: item.pop("validator_result"), "missing_validator_result"),
        ("FUWS-CORR-007", lambda item: item["validator_result"].__setitem__("validation_result", "fail"), "validator_failed"),
        ("FUWS-CORR-008", lambda item: item["observed_effect"].__setitem__("forbidden_mutations", ["repo/extra.json"]), "forbidden_path_mutation"),
        ("FUWS-CORR-009", lambda item: item["authority_lineage"].pop("final_truth"), "missing_final_truth"),
        ("FUWS-CORR-010", lambda item: item["authority_lineage"]["run"].__setitem__("run_id", "other"), "canonical_run_id_drift"),
    ],
)
def test_corruption_matrix_fails_closed(tmp_path: Path, corruption_id: str, mutate: object, expected: str) -> None:
    """Layer: contract. Verifies missing or corrupted authority evidence blocks witness success."""
    live = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved")
    bundle = _bundle_from_live(tmp_path / "workspace", live)

    mutate(bundle)
    bundle["contract_verdict"] = build_contract_verdict(copy.deepcopy(bundle))
    report = verify_trusted_repo_change_bundle_payload(bundle)

    assert report["observed_result"] == "failure", corruption_id
    assert expected in report["missing_evidence"], corruption_id


def test_replay_and_text_overclaims_downgrade(tmp_path: Path) -> None:
    """Layer: contract. Verifies unsupported higher claims remain forbidden."""
    first = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved", run_index=1)
    second = execute_trusted_repo_change(workspace_root=tmp_path / "workspace", scenario="approved", run_index=2)
    campaign = build_trusted_repo_change_campaign_report([first["witness_report"], second["witness_report"]])

    replay = evaluate_trusted_repo_change_offline_claim(campaign, requested_claims=["replay_deterministic"])
    text = evaluate_trusted_repo_change_offline_claim(campaign, requested_claims=["text_deterministic"])

    assert replay["claim_status"] == "downgraded"
    assert replay["claim_tier"] == TARGET_CLAIM_TIER
    assert _forbidden_reasons(replay, "replay_deterministic") == ["replay_evidence_missing"]
    assert text["claim_status"] == "downgraded"
    assert _forbidden_reasons(text, "text_deterministic") == ["text_identity_evidence_missing"]


def test_cli_commands_write_diff_ledger_outputs(tmp_path: Path) -> None:
    """Layer: integration. Verifies the new CLIs write stable diff-ledger JSON reports."""
    live_output = tmp_path / "live.json"
    campaign_output = tmp_path / "campaign.json"
    offline_output = tmp_path / "offline.json"
    workspace = tmp_path / "workspace"

    live_exit = run_trusted_repo_change_main(["--workspace-root", str(workspace), "--output", str(live_output)])
    campaign_exit = run_trusted_repo_change_campaign_main(["--workspace-root", str(workspace), "--output", str(campaign_output)])
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
