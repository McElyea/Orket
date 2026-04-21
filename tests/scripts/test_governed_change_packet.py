from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.proof.governed_change_packet_trusted_kernel import build_governed_change_packet_trusted_kernel_report
from scripts.proof.governed_change_packet_verifier import verify_governed_change_packet_payload
from scripts.proof.governed_change_packet_workflow import run_governed_repo_change_packet_flow
from scripts.proof.run_governed_change_packet_adversarial_benchmark import build_governed_change_packet_adversarial_benchmark
from scripts.proof.verify_governed_change_packet import main as verify_governed_change_packet_main


def test_trusted_kernel_model_passes_and_checks_all_frozen_invariants() -> None:
    """Layer: contract. Verifies the bounded trusted-kernel model checks the five frozen safety properties."""  # noqa: E501
    report = build_governed_change_packet_trusted_kernel_report()

    assert report["observed_result"] == "success"
    assert report["model_surface"] == "bounded_python_state_machine"
    assert {item["status"] for item in report["checks"]} == {"pass"}
    assert report["reachable_state_count"] >= 1


def test_packet_flow_builds_valid_packet_and_verifier_report(tmp_path: Path) -> None:
    """Layer: integration. Verifies the repo-change slice emits a packet and a valid standalone verifier report."""  # noqa: E501
    outputs = _output_paths(tmp_path)

    result = run_governed_repo_change_packet_flow(
        workspace_root=tmp_path / "workspace",
        live_output=outputs["live"],
        second_live_output=outputs["live_02"],
        campaign_output=outputs["campaign"],
        offline_output=outputs["offline"],
        denial_output=outputs["denial"],
        validator_failure_output=outputs["validator_failure"],
        packet_output=outputs["packet"],
        kernel_model_output=outputs["kernel"],
        verify_output=outputs["verifier"],
    )

    packet = result["packet"]
    verifier = result["packet_verifier"]
    assert packet["observed_result"] == "success"
    assert packet["claim_summary"]["current_truthful_claim_ceiling"] == "verdict_deterministic"
    assert verifier["packet_verdict"] == "valid"
    assert verifier["observed_result"] == "success"
    assert {item["status"] for item in verifier["required_role_diagnostics"]} == {"pass"}
    assert {item["status"] for item in verifier["authority_ref_diagnostics"]} == {"pass"}
    assert verifier["claim_diagnostics"]["requested_claim_allowed"] is True
    required_roles = {item["role"] for item in packet["artifact_manifest"] if item.get("required")}
    assert {
        "approved_live_proof",
        "flow_request",
        "run_authority",
        "validator_report",
        "witness_bundle",
        "campaign_report",
        "offline_verifier_report",
        "trusted_kernel_model_check",
    } <= required_roles


def test_packet_verifier_rejects_target_artifact_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies summary drift against authority artifacts fails the packet as invalid."""  # noqa: E501
    packet = _build_packet(tmp_path)
    packet["primary_operator_summary"]["target_artifact_path"] = "repo/config/other.json"

    report = verify_governed_change_packet_payload(packet)

    assert report["packet_verdict"] == "invalid"
    assert "packet_target_artifact_mismatch" in report["contradictions"]


def test_packet_verifier_reports_insufficient_evidence_on_overclaim(tmp_path: Path) -> None:
    """Layer: contract. Verifies replay overclaim downgrades the packet to insufficient evidence."""  # noqa: E501
    packet = _build_packet(tmp_path)
    packet["claim_summary"]["requested_claim_tier"] = "replay_deterministic"

    report = verify_governed_change_packet_payload(packet)

    assert report["packet_verdict"] == "insufficient_evidence"
    assert report["claim_tier"] == "verdict_deterministic"
    assert report["missing_evidence"] == ["requested_claim_not_allowed:replay_deterministic"]
    assert "requested_claim_not_allowed:replay_deterministic" in report["claim_diagnostics"]["downgrade_or_rejection_reasons"]


def test_packet_verifier_reports_missing_validator_role_as_insufficient(tmp_path: Path) -> None:
    """Layer: contract. Verifies a structurally coherent packet without a required validator ref fails closed as insufficient evidence."""  # noqa: E501
    packet = _build_packet(tmp_path)
    packet["artifact_manifest"] = [item for item in packet["artifact_manifest"] if item.get("role") != "validator_report"]

    report = verify_governed_change_packet_payload(packet)

    assert report["packet_verdict"] == "insufficient_evidence"
    assert "packet_missing_required_role:validator_report" in report["missing_evidence"]
    validator_diagnostic = next(item for item in report["required_role_diagnostics"] if item["role"] == "validator_report")
    assert validator_diagnostic["status"] == "missing"


def test_packet_verifier_rejects_authority_ref_digest_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies authority-ref digest drift fails closed as an invalid packet."""
    packet = _build_packet(tmp_path)
    for item in packet["artifact_manifest"]:
        if item.get("role") == "witness_bundle":
            item["digest"] = "sha256:bad"
            break

    report = verify_governed_change_packet_payload(packet)

    assert report["packet_verdict"] == "invalid"
    assert "packet_ref_digest_mismatch:witness_bundle" in report["contradictions"]
    witness_diagnostic = next(item for item in report["authority_ref_diagnostics"] if item["role"] == "witness_bundle")
    assert witness_diagnostic["status"] == "digest_mismatch"


def test_packet_verifier_cli_writes_diff_ledger_output(tmp_path: Path) -> None:
    """Layer: integration. Verifies the standalone packet-verifier CLI writes a stable diff-ledger JSON report."""  # noqa: E501
    packet = _build_packet(tmp_path)
    packet_path = tmp_path / "packet.json"
    verifier_path = tmp_path / "packet_verifier.json"
    packet_path.write_text(json.dumps(packet, indent=2, ensure_ascii=True), encoding="utf-8")

    exit_code = verify_governed_change_packet_main(["--input", str(packet_path), "--output", str(verifier_path)])

    assert exit_code == 0
    persisted = json.loads(verifier_path.read_text(encoding="utf-8"))
    assert persisted["packet_verdict"] == "valid"
    assert isinstance(persisted.get("diff_ledger"), list)


def test_adversarial_benchmark_catches_frozen_failure_classes(tmp_path: Path) -> None:
    """Layer: integration. Verifies the initial adversarial packet corpus fails closed on every frozen benchmark case."""  # noqa: E501
    benchmark = build_governed_change_packet_adversarial_benchmark(workspace_root=tmp_path / "workspace")

    assert benchmark["observed_result"] == "success"
    assert benchmark["summary"]["case_count"] == 6
    assert benchmark["summary"]["caught_count"] == 6


def _build_packet(tmp_path: Path) -> dict[str, object]:
    outputs = _output_paths(tmp_path)
    result = run_governed_repo_change_packet_flow(
        workspace_root=tmp_path / "workspace",
        live_output=outputs["live"],
        second_live_output=outputs["live_02"],
        campaign_output=outputs["campaign"],
        offline_output=outputs["offline"],
        denial_output=outputs["denial"],
        validator_failure_output=outputs["validator_failure"],
        packet_output=outputs["packet"],
        kernel_model_output=outputs["kernel"],
        verify_output=None,
    )
    return copy.deepcopy(result["packet"])


def _output_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "live": tmp_path / "trusted_repo_change_live_run.json",
        "live_02": tmp_path / "trusted_repo_change_live_run_02.json",
        "campaign": tmp_path / "trusted_repo_change_witness_verification.json",
        "offline": tmp_path / "trusted_repo_change_offline_verifier.json",
        "denial": tmp_path / "trusted_repo_change_denial.json",
        "validator_failure": tmp_path / "trusted_repo_change_validator_failure.json",
        "packet": tmp_path / "governed_repo_change_packet.json",
        "kernel": tmp_path / "governed_change_packet_trusted_kernel_model.json",
        "verifier": tmp_path / "governed_repo_change_packet_verifier.json",
    }
