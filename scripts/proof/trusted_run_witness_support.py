from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from scripts.productflow.productflow_support import (
    PRODUCTFLOW_BUILDER_SEAT,
    PRODUCTFLOW_EPIC_ID,
    PRODUCTFLOW_ISSUE_ID,
    PRODUCTFLOW_OUTPUT_CONTENT,
    PRODUCTFLOW_OUTPUT_PATH,
    relative_to_workspace,
    resolve_productflow_run_with_engine,
)
from scripts.proof.trusted_run_witness_contract import (
    APPROVAL_REASON,
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    CONTRACT_VERDICT_SCHEMA_VERSION,
    DEFAULT_BUNDLE_NAME,
    DEFAULT_VERIFICATION_OUTPUT,
    EXPECTED_ISSUE_STATUS,
    FALLBACK_CLAIM_TIER,
    MUST_CATCH_OUTCOMES,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    blocked_report,
    build_campaign_verification_report,
    build_contract_verdict,
    now_utc_iso,
    relative_to_repo,
    stable_json_digest,
    verify_witness_bundle_payload,
)


async def build_witness_bundle_payload(*, paths: Any, engine: Any, run_id: str) -> dict[str, Any]:
    resolved = await resolve_productflow_run_with_engine(
        run_id=run_id,
        engine=engine,
        workspace_root=paths.workspace_root,
    )
    approval = await _load_single_productflow_approval(engine=engine, session_id=resolved.session_id, run_id=run_id)
    issue = await engine.cards.get_by_id(PRODUCTFLOW_ISSUE_ID)
    issue_status = _issue_status(issue)
    output_path = paths.workspace_root / PRODUCTFLOW_OUTPUT_PATH
    output_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    target_run = _as_dict(approval.get("control_plane_target_run"))
    checkpoint = _as_dict(approval.get("control_plane_target_checkpoint"))
    policy_digest = str(checkpoint.get("policy_digest") or checkpoint.get("acceptance_evaluated_policy_digest") or "")
    authority_lineage = _authority_lineage(approval=approval, target_run=target_run)
    artifact_refs = _artifact_refs(
        run_summary_path=resolved.run_summary_path,
        output_path=output_path,
        workspace_root=paths.workspace_root,
    )
    control_bundle = {
        "policy_digest": policy_digest,
        "policy_snapshot_ref": str(target_run.get("policy_snapshot_id") or ""),
        "configuration_snapshot_ref": str(target_run.get("configuration_snapshot_id") or ""),
        "checkpoint_id": str(checkpoint.get("checkpoint_id") or ""),
    }
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"trusted-run-bundle:{resolved.run_id}",
        "recorded_at_utc": now_utc_iso(),
        "run_id": resolved.run_id,
        "session_id": resolved.session_id,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "policy_digest": policy_digest,
        "policy_snapshot_ref": str(target_run.get("policy_snapshot_id") or ""),
        "configuration_snapshot_ref": str(target_run.get("configuration_snapshot_id") or ""),
        "control_bundle_ref": f"runs/{resolved.session_id}/run_summary.json#control_plane;approval:{approval.get('approval_id')}",
        "control_bundle_digest": stable_json_digest(control_bundle),
        "resolution_basis": dict(resolved.resolution_basis),
        "productflow_slice": {
            "epic_id": PRODUCTFLOW_EPIC_ID,
            "issue_id": PRODUCTFLOW_ISSUE_ID,
            "builder_seat": PRODUCTFLOW_BUILDER_SEAT,
            "approval_reason": APPROVAL_REASON,
        },
        "artifact_refs": artifact_refs,
        "authority_lineage": authority_lineage,
        "observed_effect": {
            "expected_output_artifact_path": PRODUCTFLOW_OUTPUT_PATH,
            "actual_output_artifact_path": relative_to_workspace(output_path, paths.workspace_root)
            if output_path.exists()
            else "",
            "output_exists": output_path.exists(),
            "expected_normalized_content": PRODUCTFLOW_OUTPUT_CONTENT,
            "normalized_content": output_text.strip(),
            "content_sha256": _text_sha256(output_text) if output_path.exists() else "",
            "expected_issue_status": EXPECTED_ISSUE_STATUS,
            "issue_status": issue_status,
        },
    }
    bundle["contract_verdict"] = build_contract_verdict(bundle)
    return bundle


async def _load_single_productflow_approval(*, engine: Any, session_id: str, run_id: str) -> dict[str, Any]:
    approvals = await engine.list_approvals(session_id=session_id, limit=1000)
    matches = [
        item
        for item in approvals
        if str(item.get("control_plane_target_ref") or "").strip() == run_id
        and str(item.get("reason") or "").strip() == APPROVAL_REASON
    ]
    if len(matches) != 1:
        raise ValueError(f"trusted_run_productflow_approval_match_count:{len(matches)}")
    return dict(matches[0])


def _authority_lineage(*, approval: dict[str, Any], target_run: dict[str, Any]) -> dict[str, Any]:
    payload = _as_dict(approval.get("payload"))
    return {
        "governed_input": {
            "epic_id": PRODUCTFLOW_EPIC_ID,
            "issue_id": PRODUCTFLOW_ISSUE_ID,
            "seat": PRODUCTFLOW_BUILDER_SEAT,
            "payload_digest": stable_json_digest(payload),
        },
        "run": target_run,
        "step": _as_dict(approval.get("control_plane_target_step")),
        "approval_request": {
            "approval_id": str(approval.get("approval_id") or ""),
            "status": str(approval.get("status") or ""),
            "request_type": str(approval.get("request_type") or ""),
            "gate_mode": str(approval.get("gate_mode") or ""),
            "reason": str(approval.get("reason") or ""),
            "control_plane_target_ref": str(approval.get("control_plane_target_ref") or ""),
            "payload_digest": stable_json_digest(payload),
        },
        "operator_action": _as_dict(approval.get("control_plane_target_operator_action")),
        "checkpoint": _as_dict(approval.get("control_plane_target_checkpoint")),
        "resource": _as_dict(approval.get("control_plane_target_resource")),
        "reservation": _as_dict(approval.get("control_plane_target_reservation")),
        "effect_journal": _as_dict(approval.get("control_plane_target_effect_journal")),
        "final_truth": _as_dict(approval.get("control_plane_target_final_truth")),
    }


def _artifact_refs(*, run_summary_path: Path, output_path: Path, workspace_root: Path) -> list[dict[str, Any]]:
    return [
        _artifact_ref(kind="run_summary", path=run_summary_path, workspace_root=workspace_root),
        _artifact_ref(kind="output_artifact", path=output_path, workspace_root=workspace_root),
    ]


def _artifact_ref(*, kind: str, path: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": relative_to_workspace(path, workspace_root) if path.exists() else "",
        "digest": _file_sha256(path) if path.exists() else "",
        "exists": path.exists(),
    }


def _issue_status(issue: Any) -> str:
    status = getattr(issue, "status", None)
    return status.value if hasattr(status, "value") else str(status or "")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _text_sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
