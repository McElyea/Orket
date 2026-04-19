from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.check_trusted_terraform_publication_readiness import (
    build_publication_readiness_report,
    main,
)
from scripts.proof.trusted_terraform_plan_decision_contract import TRUSTED_TERRAFORM_COMPARE_SCOPE


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _foundation(path: Path) -> Path:
    return _write(
        path,
        {
            "schema_version": "trusted_run_proof_foundation.v1",
            "observed_result": "success",
            "foundation_targets": [{"target": f"target-{index}", "status": "pass"} for index in range(6)],
        },
    )


def _campaign(path: Path) -> Path:
    return _write(
        path,
        {
            "schema_version": "trusted_run_witness_report.v1",
            "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
            "observed_result": "success",
            "claim_tier": "verdict_deterministic",
            "run_count": 2,
        },
    )


def _offline(path: Path) -> Path:
    return _write(
        path,
        {
            "schema_version": "offline_trusted_run_verifier.v1",
            "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
            "observed_result": "success",
            "claim_status": "allowed",
            "claim_tier": "verdict_deterministic",
        },
    )


def _runtime(path: Path, *, observed_result: str = "success", reason: str = "") -> Path:
    return _write(
        path,
        {
            "schema_version": "trusted_terraform_plan_decision_live_runtime.v1",
            "compare_scope": TRUSTED_TERRAFORM_COMPARE_SCOPE,
            "observed_result": observed_result,
            "execution_status": "environment_blocker" if observed_result == "environment blocker" else "success",
            "reason": reason,
            "witness_bundle_ref": "workspace/trusted_terraform_plan_decision/runs/session/trusted_run_witness_bundle.json",
            "witness_report": {"observed_result": "success"},
        },
    )


def test_publication_readiness_blocks_on_provider_backed_environment_blocker(tmp_path: Path) -> None:
    """Layer: contract. Verifies Terraform publication readiness fails closed on environment-blocked provider proof."""
    report = build_publication_readiness_report(
        foundation_input=_foundation(tmp_path / "foundation.json"),
        campaign_input=_campaign(tmp_path / "campaign.json"),
        offline_input=_offline(tmp_path / "offline.json"),
        runtime_input=_runtime(tmp_path / "runtime.json", observed_result="environment blocker", reason="missing_required_env:AWS_REGION"),
    )

    assert report["observed_result"] == "environment blocker"
    assert report["publication_decision"] == "blocked"
    assert report["public_trust_slice_action"] == "do_not_widen_public_trust_slice"
    assert "runtime_environment_blocker:missing_required_env:AWS_REGION" in report["blocking_reasons"]


def test_publication_readiness_allows_only_complete_success_evidence(tmp_path: Path) -> None:
    """Layer: contract. Verifies the gate permits boundary-update readiness only when all evidence checks pass."""
    report = build_publication_readiness_report(
        foundation_input=_foundation(tmp_path / "foundation.json"),
        campaign_input=_campaign(tmp_path / "campaign.json"),
        offline_input=_offline(tmp_path / "offline.json"),
        runtime_input=_runtime(tmp_path / "runtime.json"),
    )

    assert report["observed_result"] == "success"
    assert report["publication_decision"] == "ready_for_publication_boundary_update"
    assert report["claim_tier_ceiling"] == "verdict_deterministic"
    assert report["failed_checks"] == []


def test_publication_readiness_cli_writes_diff_ledger(tmp_path: Path) -> None:
    """Layer: integration. Verifies the readiness CLI writes a stable diff-ledger JSON report."""
    output = tmp_path / "readiness.json"

    exit_code = main(
        [
            "--foundation-input",
            str(_foundation(tmp_path / "foundation.json")),
            "--campaign-input",
            str(_campaign(tmp_path / "campaign.json")),
            "--offline-input",
            str(_offline(tmp_path / "offline.json")),
            "--runtime-input",
            str(_runtime(tmp_path / "runtime.json")),
            "--output",
            str(output),
        ]
    )

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert persisted["publication_decision"] == "ready_for_publication_boundary_update"
    assert isinstance(persisted.get("diff_ledger"), list)
