from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.application.services.outward_run_execution_plan import acceptance_tool_steps
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_runs import OutwardRunRecord
from scripts.proof.outward_run_witness_contract import (
    ADMITTED_COMPARE_SCOPES,
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    COMPARE_SCOPE_DENIED,
    COMPARE_SCOPE_POLICY_REJECTED,
    DEFAULT_BUNDLE_PATH,
    DEFAULT_COMMITTED_ARTIFACT_PATH,
    DEFAULT_LEDGER_EXPORT_PATH,
    OPERATOR_SURFACE,
    PACKAGE_SCHEMA_VERSION,
    canonical_json_digest,
    compute_package_digest,
    file_sha256,
)


class OutwardWitnessBuildError(RuntimeError):
    pass


async def build_outward_run_witness_package(
    *,
    db_path: Path,
    workspace_root: Path,
    run_id: str,
    output_dir: Path,
    scope: str = COMPARE_SCOPE,
) -> dict[str, Any]:
    clean_scope = _normalize_scope(scope)
    run_store = OutwardRunStore(db_path)
    approval_store = OutwardApprovalStore(db_path)
    event_store = OutwardRunEventStore(db_path)
    run = await run_store.get(run_id)
    if run is None:
        raise OutwardWitnessBuildError("run_not_found")
    approvals = await approval_store.list(run_id=run.run_id, limit=500)
    ledger = await OutwardLedgerService(
        run_store=run_store,
        event_store=event_store,
        utc_now=lambda: "",
    ).export(run.run_id, types=("all",), include_pii=False, record_request=False)

    artifact_target = output_dir / DEFAULT_COMMITTED_ARTIFACT_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / DEFAULT_LEDGER_EXPORT_PATH, ledger)
    if clean_scope in {COMPARE_SCOPE_DENIED, COMPARE_SCOPE_POLICY_REJECTED}:
        if clean_scope == COMPARE_SCOPE_DENIED:
            _ensure_denial_has_no_effect_artifacts(run, approvals, ledger)
        else:
            _ensure_policy_rejection_has_no_effect_artifacts(run, approvals, ledger)
        if artifact_target.exists():
            artifact_target.unlink()
        artifact_source = None
        artifact_digest = ""
    else:
        artifact_source = _committed_output_source(run, workspace_root)
        artifact_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact_source, artifact_target)
        artifact_digest = file_sha256(artifact_target)

    bundle = _build_bundle(
        run=run,
        approvals=approvals,
        ledger=ledger,
        workspace_root=workspace_root,
        output_dir=output_dir,
        scope=clean_scope,
        artifact_source=artifact_source,
        artifact_digest=artifact_digest,
    )
    _write_json(output_dir / DEFAULT_BUNDLE_PATH, bundle)
    manifest = _build_manifest(output_dir=output_dir, scope=clean_scope, package_id=f"package:{run.run_id}")
    _write_json(output_dir / "manifest.json", manifest)
    return {"package_path": str(output_dir), "run_id": run.run_id, "compare_scope": clean_scope}


def _build_bundle(
    *,
    run: OutwardRunRecord,
    approvals: list[OutwardApprovalProposal],
    ledger: dict[str, Any],
    workspace_root: Path,
    output_dir: Path,
    scope: str,
    artifact_source: Path | None,
    artifact_digest: str,
) -> dict[str, Any]:
    approval = _selected_approval(approvals, scope)
    proposal_event = _first_event(ledger, "proposal_made")
    policy_rejection_event = _first_event(ledger, "proposal_policy_rejected")
    tool_event = _first_event(ledger, "tool_invoked")
    policy_payload = policy_rejection_event.get("payload") if isinstance(policy_rejection_event.get("payload"), dict) else {}
    proposal_payload = proposal_event.get("payload") if isinstance(proposal_event.get("payload"), dict) else {}
    tool_payload = tool_event.get("payload") if isinstance(tool_event.get("payload"), dict) else {}
    tool_name = str(
        tool_payload.get("connector_name")
        or policy_payload.get("tool_name")
        or policy_payload.get("tool")
        or (approval.tool if approval else "")
    )
    tool_args_digest = str(tool_payload.get("args_hash") or policy_payload.get("tool_args_hash") or proposal_payload.get("tool_args_hash") or "")
    artifact_refs: list[dict[str, Any]] = []
    package_refs: dict[str, Any] = {"ledger_export_path": DEFAULT_LEDGER_EXPORT_PATH}
    if artifact_source is not None:
        artifact_refs.append(
            {
                "artifact_role": "committed_output",
                "path": _relative_or_absolute(artifact_source, workspace_root),
                "package_path": DEFAULT_COMMITTED_ARTIFACT_PATH,
                "digest": artifact_digest,
                "classification": "authority",
            }
        )
        package_refs["committed_output_path"] = DEFAULT_COMMITTED_ARTIFACT_PATH
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"bundle:{run.run_id}",
        "run_id": run.run_id,
        "produced_at_iso": "",
        "compare_scope": scope,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier_request": "outward_lab_only",
        "run_authority": _run_authority(run),
        "approval_authority": [_approval_authority(item, tool_args_digest) for item in approvals],
        "policy_rejection_authority": (
            [_policy_rejection_authority(run, policy_rejection_event, tool_name, tool_args_digest)]
            if scope == COMPARE_SCOPE_POLICY_REJECTED
            else []
        ),
        "ledger_evidence": _ledger_evidence(ledger, output_dir),
        "effect_evidence": [_effect_evidence(run, approval, tool_event, tool_name, tool_args_digest)] if tool_event else [],
        "model_invocation_evidence": [_model_evidence(workspace_root, proposal_event)] if proposal_event else [],
        "policy_identity": _policy_identity(run),
        "artifact_refs": artifact_refs,
        "package_refs": package_refs,
    }
    return bundle


def _run_authority(run: OutwardRunRecord) -> dict[str, Any]:
    steps = acceptance_tool_steps(run)
    return {
        "run_id": run.run_id,
        "namespace": run.namespace,
        "status": run.status,
        "run_status": run.status,
        "submitted_at_iso": run.submitted_at,
        "task_description": str(run.task.get("description") or ""),
        "task_instruction": str(run.task.get("instruction") or ""),
        "acceptance_contract_tool": str(steps[0].get("tool") or "") if steps else None,
        "acceptance_contract_sequence": [str(step.get("tool") or "") for step in steps] if len(steps) > 1 else None,
        "policy_overrides_digest": canonical_json_digest(run.policy_overrides),
        "run_record_digest": canonical_json_digest(_run_record_payload(run)),
    }


def _approval_authority(proposal: OutwardApprovalProposal, tool_args_digest: str) -> dict[str, Any]:
    return {
        "approval_id": proposal.proposal_id,
        "run_id": proposal.run_id,
        "turn_index": 1,
        "tool_name": proposal.tool,
        "tool_args_digest": tool_args_digest,
        "status": proposal.status,
        "decided_at_iso": proposal.decided_at,
        "approval_record_digest": canonical_json_digest(proposal.to_decision_payload()),
    }


def _policy_rejection_authority(
    run: OutwardRunRecord,
    event: dict[str, Any],
    tool_name: str,
    tool_args_digest: str,
) -> dict[str, Any]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    proposal_ref = str(payload.get("proposal_ref") or _legacy_proposal_ref(run.run_id, event, tool_name, tool_args_digest))
    return {
        "proposal_ref": proposal_ref,
        "run_id": run.run_id,
        "turn_index": int(event.get("turn") or run.current_turn or 1),
        "tool_name": tool_name,
        "tool_args_digest": tool_args_digest,
        "policy_result": str(payload.get("policy_result") or ""),
        "reason": str(payload.get("reason") or ""),
        "event_position": int(event.get("position") or 0),
        "policy_event_payload_digest": canonical_json_digest(payload),
    }


def _ledger_evidence(ledger: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    canonical = ledger.get("canonical") if isinstance(ledger.get("canonical"), dict) else {}
    return {
        "ledger_export_schema": ledger.get("schema_version"),
        "run_id": ledger.get("run_id"),
        "event_count": canonical.get("event_count"),
        "export_scope": ledger.get("export_scope"),
        "ledger_hash": canonical.get("ledger_hash"),
        "events": [_event_summary(event) for event in ledger.get("events") or [] if isinstance(event, dict)],
        "ledger_export_digest": file_sha256(output_dir / DEFAULT_LEDGER_EXPORT_PATH),
        "ledger_export_package_path": DEFAULT_LEDGER_EXPORT_PATH,
    }


def _effect_evidence(
    run: OutwardRunRecord,
    approval: OutwardApprovalProposal | None,
    tool_event: dict[str, Any],
    tool_name: str,
    tool_args_digest: str,
) -> dict[str, Any]:
    return {
        "event_type": "tool_invoked",
        "run_id": run.run_id,
        "approval_id": approval.proposal_id if approval else "",
        "turn_index": int(tool_event.get("turn") or run.current_turn or 1),
        "tool_name": tool_name,
        "tool_args_digest": tool_args_digest,
        "connector_result_digest": canonical_json_digest((tool_event.get("payload") or {}).get("result_summary") or {}),
        "sequence_index": int(tool_event.get("position") or 0),
    }


def _model_evidence(workspace_root: Path, proposal_event: dict[str, Any]) -> dict[str, Any]:
    payload = proposal_event.get("payload") if isinstance(proposal_event.get("payload"), dict) else {}
    turn = int(proposal_event.get("turn") or 1)
    invocation_ref = str(payload.get("model_invocation_ref") or "").strip()
    invocation_path = _resolve_workspace_ref(workspace_root, invocation_ref)
    if not invocation_path.exists():
        raise OutwardWitnessBuildError("model_invocation_source_missing")
    evidence_dir = invocation_path.parent
    prompt_digest = str(payload.get("model_prompt_redacted_sha256") or _optional_file_digest(evidence_dir / f"model_prompt_redacted_turn_{turn}.json"))
    extraction_digest = str(payload.get("proposal_extraction_sha256") or _optional_file_digest(evidence_dir / f"proposal_extraction_turn_{turn}.json"))
    return {
        "turn_index": turn,
        "model_provider": str(payload.get("provider_name") or ""),
        "model_name": str(payload.get("model_name") or ""),
        "model_invocation_digest": str(payload.get("model_invocation_sha256") or file_sha256(invocation_path)),
        "model_prompt_redacted_digest": prompt_digest,
        "model_response_redacted_digest": str(payload.get("model_response_content_sha256") or ""),
        "proposal_extraction_digest": extraction_digest,
    }


def _policy_identity(run: OutwardRunRecord) -> dict[str, Any]:
    return {
        "policy_overrides_digest": canonical_json_digest(run.policy_overrides),
        "approval_required_tools": list(run.policy_overrides.get("approval_required_tools") or []),
        "max_turns": int(run.policy_overrides.get("max_turns") or run.max_turns),
        "approval_timeout_seconds": int(run.policy_overrides.get("approval_timeout_seconds") or 300),
    }


def _committed_output_source(run: OutwardRunRecord, workspace_root: Path) -> Path:
    state = run.task.get("_outward_execution_state")
    results = state.get("tool_results") if isinstance(state, dict) else []
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict) or item.get("tool") != "write_file":
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        raw_path = str(result.get("path") or "").strip()
        if raw_path:
            path = Path(raw_path)
            resolved = path if path.is_absolute() else (workspace_root / path).resolve()
            if not resolved.exists():
                raise OutwardWitnessBuildError("committed_artifact_missing")
            return resolved
    raise OutwardWitnessBuildError("committed_artifact_missing")


def _normalize_scope(scope: str) -> str:
    clean_scope = str(scope or COMPARE_SCOPE).strip() or COMPARE_SCOPE
    if clean_scope not in ADMITTED_COMPARE_SCOPES:
        raise OutwardWitnessBuildError("unsupported_compare_scope")
    return clean_scope


def _selected_approval(approvals: list[OutwardApprovalProposal], scope: str) -> OutwardApprovalProposal | None:
    if scope == COMPARE_SCOPE_POLICY_REJECTED:
        return None
    if scope == COMPARE_SCOPE_DENIED:
        for approval in approvals:
            if approval.status == "denied":
                return approval
    return approvals[0] if approvals else None


def _ensure_denial_has_no_effect_artifacts(
    run: OutwardRunRecord,
    approvals: list[OutwardApprovalProposal],
    ledger: dict[str, Any],
) -> None:
    if _selected_approval(approvals, COMPARE_SCOPE_DENIED) is None:
        raise OutwardWitnessBuildError("denial_approval_missing")
    state = run.task.get("_outward_execution_state")
    results = state.get("tool_results") if isinstance(state, dict) else []
    if isinstance(results, list) and any(isinstance(item, dict) for item in results):
        raise OutwardWitnessBuildError("denied_effect_state_present")
    denial_position = _first_position(ledger, "proposal_denied")
    if denial_position is None:
        raise OutwardWitnessBuildError("denial_event_missing")
    for event in ledger.get("events") or []:
        if not isinstance(event, dict) or int(event.get("position") or 0) <= denial_position:
            continue
        if event.get("event_type") in {"tool_invoked", "commitment_recorded"}:
            raise OutwardWitnessBuildError("denied_effect_event_present")


def _ensure_policy_rejection_has_no_effect_artifacts(
    run: OutwardRunRecord,
    approvals: list[OutwardApprovalProposal],
    ledger: dict[str, Any],
) -> None:
    if approvals:
        raise OutwardWitnessBuildError("policy_rejected_approval_authority_present")
    state = run.task.get("_outward_execution_state")
    results = state.get("tool_results") if isinstance(state, dict) else []
    if isinstance(results, list) and any(isinstance(item, dict) for item in results):
        raise OutwardWitnessBuildError("policy_rejected_effect_state_present")
    rejected_position = _first_position(ledger, "proposal_policy_rejected")
    if rejected_position is None:
        raise OutwardWitnessBuildError("policy_rejection_event_missing")
    for event in ledger.get("events") or []:
        if not isinstance(event, dict) or int(event.get("position") or 0) <= rejected_position:
            continue
        if event.get("event_type") in {"proposal_pending_approval", "proposal_approved", "tool_invoked", "commitment_recorded"}:
            raise OutwardWitnessBuildError("policy_rejected_effect_event_present")


def _resolve_workspace_ref(workspace_root: Path, ref: str) -> Path:
    root = workspace_root.resolve()
    resolved = (root / ref).resolve()
    if not resolved.is_relative_to(root):
        raise OutwardWitnessBuildError("workspace_ref_outside_root")
    return resolved


def _optional_file_digest(path: Path) -> str:
    return file_sha256(path) if path.exists() else ""


def _first_event(ledger: dict[str, Any], event_type: str) -> dict[str, Any]:
    for event in ledger.get("events") or []:
        if isinstance(event, dict) and event.get("event_type") == event_type:
            return event
    return {}


def _first_position(ledger: dict[str, Any], event_type: str) -> int | None:
    event = _first_event(ledger, event_type)
    return int(event.get("position") or 0) if event else None


def _event_summary(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event.get("event_type"),
        "position": event.get("position"),
        "sequence_index": event.get("position"),
        "event_hash": event.get("event_hash"),
        "previous_chain_hash": event.get("previous_chain_hash"),
        "chain_hash": event.get("chain_hash"),
        "event_payload_digest": canonical_json_digest(event.get("payload") or {}),
    }


def _legacy_proposal_ref(run_id: str, event: dict[str, Any], tool_name: str, tool_args_digest: str) -> str:
    return f"model_proposal:{run_id}:{int(event.get('turn') or 1)}:{tool_name}:{tool_args_digest}"


def _run_record_payload(run: OutwardRunRecord) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "status": run.status,
        "namespace": run.namespace,
        "submitted_at": run.submitted_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "stop_reason": run.stop_reason,
        "current_turn": run.current_turn,
        "max_turns": run.max_turns,
        "task": run.task,
        "policy_overrides": run.policy_overrides,
        "pending_proposals": list(run.pending_proposals),
    }


def _build_manifest(*, output_dir: Path, scope: str, package_id: str) -> dict[str, Any]:
    artifact_paths: dict[str, str] = {}
    file_digests = {
        DEFAULT_BUNDLE_PATH: file_sha256(output_dir / DEFAULT_BUNDLE_PATH),
        DEFAULT_LEDGER_EXPORT_PATH: file_sha256(output_dir / DEFAULT_LEDGER_EXPORT_PATH),
    }
    artifact_path = output_dir / DEFAULT_COMMITTED_ARTIFACT_PATH
    if artifact_path.exists():
        artifact_paths["committed_output"] = DEFAULT_COMMITTED_ARTIFACT_PATH
        file_digests[DEFAULT_COMMITTED_ARTIFACT_PATH] = file_sha256(artifact_path)
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "compare_scope": scope,
        "bundle_path": DEFAULT_BUNDLE_PATH,
        "ledger_export_path": DEFAULT_LEDGER_EXPORT_PATH,
        "artifact_paths": artifact_paths,
        "file_digests": file_digests,
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    return manifest


def _relative_or_absolute(path: Path, root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
