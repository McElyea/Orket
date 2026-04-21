from __future__ import annotations

import copy
import os
import shutil
from pathlib import Path
from typing import Any

from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.proof.governed_change_packet_contract import (
    DEFAULT_GOVERNED_CHANGE_PACKET_KERNEL_MODEL_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
    DEFAULT_TRUSTED_REPO_DENIAL_OUTPUT,
    DEFAULT_TRUSTED_REPO_VALIDATOR_FAILURE_OUTPUT,
    ENTRY_PROJECTION_CLASSIFICATION,
    GOVERNED_CHANGE_PACKET_FAMILY,
    GOVERNED_CHANGE_PACKET_SCHEMA_VERSION,
    NEGATIVE_PROOF_CLASSIFICATION,
    PRIMARY_AUTHORITY_CLASSIFICATIONS,
    artifact_manifest_entry,
    default_limitations,
    load_json_object,
    packet_claim_summary,
    packet_entry_disclaimer,
    packet_id,
    packet_signature_material,
    packet_summary,
    resolve_repo_path,
    stable_signature_digest,
)
from scripts.proof.governed_change_packet_trusted_kernel import (
    build_governed_change_packet_trusted_kernel_report,
    evaluate_governed_change_packet_kernel_conformance,
)
from scripts.proof.trusted_repo_change_contract import (
    DEFAULT_CAMPAIGN_OUTPUT,
    DEFAULT_LIVE_RUN_OUTPUT,
    DEFAULT_OFFLINE_OUTPUT,
    DEFAULT_WORKSPACE_ROOT,
    TARGET_CLAIM_TIER,
    TRUSTED_REPO_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
)
from scripts.proof.trusted_repo_change_offline import evaluate_trusted_repo_change_offline_claim
from scripts.proof.trusted_repo_change_verifier import build_trusted_repo_change_campaign_report
from scripts.proof.trusted_repo_change_workflow import execute_trusted_repo_change, persist_live_run


def build_governed_repo_change_packet(
    *,
    live_path: Path,
    campaign_path: Path,
    offline_path: Path,
    kernel_model_path: Path,
    denial_path: Path | None = None,
    validator_failure_path: Path | None = None,
) -> dict[str, Any]:
    live_report = load_json_object(live_path)
    campaign_report = load_json_object(campaign_path)
    offline_report = load_json_object(offline_path)
    model_report = load_json_object(kernel_model_path)
    bundle_path = resolve_repo_path(str(live_report.get("witness_bundle_ref") or ""))
    flow_path = resolve_repo_path(str(live_report.get("flow_request_ref") or ""))
    run_authority_path = resolve_repo_path(str(live_report.get("run_authority_ref") or ""))
    validator_path = resolve_repo_path(str(live_report.get("validator_ref") or ""))
    bundle = load_json_object(bundle_path)
    flow_request = load_json_object(flow_path)
    run_authority = load_json_object(run_authority_path)
    validator_report = load_json_object(validator_path)
    artifact_refs = {
        "approved_live_proof": relative_to_repo(live_path),
        "flow_request": relative_to_repo(flow_path),
        "run_authority": relative_to_repo(run_authority_path),
        "validator_report": relative_to_repo(validator_path),
        "witness_bundle": relative_to_repo(bundle_path),
        "campaign_report": relative_to_repo(campaign_path),
        "offline_verifier_report": relative_to_repo(offline_path),
        "trusted_kernel_model_check": relative_to_repo(kernel_model_path),
    }
    conformance = evaluate_governed_change_packet_kernel_conformance(
        bundle=bundle,
        live_report=live_report,
        campaign_report=campaign_report,
        offline_report=offline_report,
        model_report=model_report,
        artifact_refs=artifact_refs,
    )
    packet = {
        "schema_version": GOVERNED_CHANGE_PACKET_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "mixed",
        "observed_path": _packet_observed_path(live_report, campaign_report, offline_report, model_report, conformance),
        "observed_result": _packet_observed_result(live_report, campaign_report, offline_report, model_report, conformance),
        "packet_family": GOVERNED_CHANGE_PACKET_FAMILY,
        "packet_id": packet_id(str(live_report.get("session_id") or "")),
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": str(live_report.get("operator_surface") or ""),
        "packet_entry_disclaimer": packet_entry_disclaimer(),
        "primary_operator_summary": packet_summary(live_report=live_report, offline_report=offline_report),
        "claim_summary": packet_claim_summary(offline_report),
        "artifact_manifest": _artifact_manifest(
            live_path=live_path,
            flow_path=flow_path,
            run_authority_path=run_authority_path,
            validator_path=validator_path,
            bundle_path=bundle_path,
            campaign_path=campaign_path,
            offline_path=offline_path,
            kernel_model_path=kernel_model_path,
            live_report=live_report,
            flow_request=flow_request,
            run_authority=run_authority,
            validator_report=validator_report,
            bundle=bundle,
            campaign_report=campaign_report,
            offline_report=offline_report,
            model_report=model_report,
            denial_path=denial_path,
            validator_failure_path=validator_failure_path,
        ),
        "trusted_kernel": {
            "model_check": model_report,
            "conformance": conformance,
        },
        "limitations": default_limitations(),
    }
    packet["packet_signature_digest"] = stable_signature_digest(packet_signature_material(packet))
    return packet


def persist_governed_change_packet(path: Path, packet: dict[str, Any]) -> dict[str, Any]:
    return write_payload_with_diff_ledger(path.resolve(), packet)


def run_governed_repo_change_packet_flow(
    *,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    live_output: Path = DEFAULT_LIVE_RUN_OUTPUT,
    second_live_output: Path | None = None,
    campaign_output: Path = DEFAULT_CAMPAIGN_OUTPUT,
    offline_output: Path = DEFAULT_OFFLINE_OUTPUT,
    denial_output: Path = DEFAULT_TRUSTED_REPO_DENIAL_OUTPUT,
    validator_failure_output: Path = DEFAULT_TRUSTED_REPO_VALIDATOR_FAILURE_OUTPUT,
    packet_output: Path = DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT,
    kernel_model_output: Path = DEFAULT_GOVERNED_CHANGE_PACKET_KERNEL_MODEL_OUTPUT,
    verify_output: Path | None = DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT,
) -> dict[str, Any]:
    from scripts.proof.governed_change_packet_verifier import verify_governed_change_packet_payload

    os.environ.setdefault("ORKET_DISABLE_SANDBOX", "1")
    workspace = workspace_root.resolve()
    _reset_fixture_workspace(workspace)
    live_output = live_output.resolve()
    second_live_output = second_live_output.resolve() if second_live_output is not None else live_output.with_name(f"{live_output.stem}_02{live_output.suffix}")
    campaign_output = campaign_output.resolve()
    offline_output = offline_output.resolve()
    denial_output = denial_output.resolve()
    validator_failure_output = validator_failure_output.resolve()
    approved = execute_trusted_repo_change(workspace_root=workspace, scenario="approved", run_index=1)
    persisted_live = persist_live_run(live_output, approved)
    second = execute_trusted_repo_change(workspace_root=workspace, scenario="approved", run_index=2)
    persisted_second = persist_live_run(second_live_output, second)
    denial = execute_trusted_repo_change(workspace_root=workspace, scenario="denied", run_index=1)
    persisted_denial = persist_live_run(denial_output, denial)
    validator_failure = execute_trusted_repo_change(workspace_root=workspace, scenario="validator_failure", run_index=1)
    persisted_validator_failure = persist_live_run(validator_failure_output, validator_failure)
    campaign = build_trusted_repo_change_campaign_report(
        [persisted_live.get("witness_report") or {}, persisted_second.get("witness_report") or {}],
        bundle_refs=[
            str(persisted_live.get("witness_bundle_ref") or ""),
            str(persisted_second.get("witness_bundle_ref") or ""),
        ],
        live_proof_refs=[relative_to_repo(live_output), relative_to_repo(second_live_output)],
    )
    persisted_campaign = write_payload_with_diff_ledger(campaign_output, campaign)
    offline = evaluate_trusted_repo_change_offline_claim(
        campaign,
        requested_claims=[TARGET_CLAIM_TIER],
        evidence_ref=relative_to_repo(campaign_output),
    )
    persisted_offline = write_payload_with_diff_ledger(offline_output, offline)
    kernel_model = build_governed_change_packet_trusted_kernel_report()
    persisted_kernel_model = write_payload_with_diff_ledger(kernel_model_output.resolve(), kernel_model)
    packet = build_governed_repo_change_packet(
        live_path=live_output,
        campaign_path=campaign_output,
        offline_path=offline_output,
        kernel_model_path=kernel_model_output.resolve(),
        denial_path=denial_output,
        validator_failure_path=validator_failure_output,
    )
    persisted_packet = persist_governed_change_packet(packet_output.resolve(), packet)
    verifier_report = {}
    if verify_output is not None:
        verifier_report = verify_governed_change_packet_payload(
            packet,
            evidence_ref=relative_to_repo(packet_output.resolve()),
        )
        verifier_report = write_payload_with_diff_ledger(verify_output.resolve(), verifier_report)
    return {
        "packet": persisted_packet,
        "packet_ref": relative_to_repo(packet_output.resolve()),
        "packet_verifier": verifier_report,
        "packet_verifier_ref": relative_to_repo(verify_output.resolve()) if verify_output is not None else "",
        "live_ref": relative_to_repo(live_output),
        "campaign_ref": relative_to_repo(campaign_output),
        "offline_ref": relative_to_repo(offline_output),
        "kernel_model_ref": relative_to_repo(kernel_model_output.resolve()),
        "denial_ref": relative_to_repo(denial_output),
        "validator_failure_ref": relative_to_repo(validator_failure_output),
    }


def _artifact_manifest(
    *,
    live_path: Path,
    flow_path: Path,
    run_authority_path: Path,
    validator_path: Path,
    bundle_path: Path,
    campaign_path: Path,
    offline_path: Path,
    kernel_model_path: Path,
    live_report: dict[str, Any],
    flow_request: dict[str, Any],
    run_authority: dict[str, Any],
    validator_report: dict[str, Any],
    bundle: dict[str, Any],
    campaign_report: dict[str, Any],
    offline_report: dict[str, Any],
    model_report: dict[str, Any],
    denial_path: Path | None,
    validator_failure_path: Path | None,
) -> list[dict[str, Any]]:
    entries = [
        artifact_manifest_entry(role="approved_live_proof", path=live_path, classification="authority_bearing", required=True, title="Approved live proof", schema_version=str(live_report.get("schema_version") or "")),
        artifact_manifest_entry(role="flow_request", path=flow_path, classification="authority_bearing", required=True, title="Governed flow request", schema_version=str(flow_request.get("schema_version") or "")),
        artifact_manifest_entry(role="run_authority", path=run_authority_path, classification="primary_authority", required=True, title="Run authority lineage", summary="Primary authority record family for approval, reservation, checkpoint, effect, and final truth."),
        artifact_manifest_entry(role="validator_report", path=validator_path, classification="authority_bearing", required=True, title="Validator report", schema_version=str(validator_report.get("schema_version") or "")),
        artifact_manifest_entry(role="witness_bundle", path=bundle_path, classification="primary_authority", required=True, title="Witness bundle", schema_version=str(bundle.get("schema_version") or "")),
        artifact_manifest_entry(role="campaign_report", path=campaign_path, classification="authority_bearing", required=True, title="Witness campaign report", schema_version=str(campaign_report.get("schema_version") or "")),
        artifact_manifest_entry(role="offline_verifier_report", path=offline_path, classification="authority_bearing", required=True, title="Offline verifier report", schema_version=str(offline_report.get("schema_version") or "")),
        artifact_manifest_entry(role="trusted_kernel_model_check", path=kernel_model_path, classification="authority_bearing", required=True, title="Trusted kernel model check", schema_version=str(model_report.get("schema_version") or "")),
    ]
    if denial_path is not None:
        entries.append(
            artifact_manifest_entry(
                role="denial_negative_proof",
                path=denial_path,
                classification=NEGATIVE_PROOF_CLASSIFICATION,
                required=False,
                title="Denial negative proof",
            )
        )
    if validator_failure_path is not None:
        entries.append(
            artifact_manifest_entry(
                role="validator_failure_negative_proof",
                path=validator_failure_path,
                classification=NEGATIVE_PROOF_CLASSIFICATION,
                required=False,
                title="Validator failure negative proof",
            )
        )
    entries.append(
        {
            "role": "operator_summary",
            "title": "Packet operator summary",
            "classification": ENTRY_PROJECTION_CLASSIFICATION,
            "required": False,
            "path": "",
            "exists": True,
            "digest": "",
            "schema_version": "",
            "summary": "Projection-only packet entry summary. Not proof authority by itself.",
        }
    )
    return entries


def _reset_fixture_workspace(workspace: Path) -> None:
    workspace = workspace.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    if workspace.parent == workspace or workspace == repo_root:
        raise ValueError("governed_packet_workspace_root_must_be_dedicated_fixture_directory")
    config_path = workspace / "repo" / "config" / "trusted-change.json"
    if not config_path.resolve().is_relative_to(workspace):
        raise ValueError("governed_packet_config_target_outside_workspace")
    if config_path.exists():
        config_path.unlink()
    runs_root = workspace / "runs"
    if not runs_root.resolve().is_relative_to(workspace) or runs_root.resolve() == workspace:
        raise ValueError("governed_packet_runs_root_outside_workspace")
    if runs_root.exists():
        shutil.rmtree(runs_root)


def _packet_observed_path(
    live_report: dict[str, Any],
    campaign_report: dict[str, Any],
    offline_report: dict[str, Any],
    model_report: dict[str, Any],
    conformance: dict[str, Any],
) -> str:
    if all(
        item
        for item in (
            live_report.get("observed_result") == "success",
            campaign_report.get("observed_result") == "success",
            offline_report.get("claim_status") == "allowed",
            model_report.get("observed_result") == "success",
            conformance.get("result") == "pass",
        )
    ):
        return "primary"
    return "blocked"


def _packet_observed_result(
    live_report: dict[str, Any],
    campaign_report: dict[str, Any],
    offline_report: dict[str, Any],
    model_report: dict[str, Any],
    conformance: dict[str, Any],
) -> str:
    statuses = [
        live_report.get("observed_result") == "success",
        campaign_report.get("observed_result") == "success",
        offline_report.get("claim_status") == "allowed" and offline_report.get("claim_tier") == TARGET_CLAIM_TIER,
        model_report.get("observed_result") == "success",
        conformance.get("result") == "pass",
    ]
    if all(statuses):
        return "success"
    if any(statuses):
        return "partial success"
    return "failure"
