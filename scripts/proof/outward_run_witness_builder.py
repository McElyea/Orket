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
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
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

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_source = _committed_output_source(run, workspace_root)
    artifact_target = output_dir / DEFAULT_COMMITTED_ARTIFACT_PATH
    artifact_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact_source, artifact_target)
    _write_json(output_dir / DEFAULT_LEDGER_EXPORT_PATH, ledger)

    bundle = _build_bundle(
        run=run,
        approvals=approvals,
        ledger=ledger,
        workspace_root=workspace_root,
        output_dir=output_dir,
        scope=scope,
        artifact_source=artifact_source,
        artifact_digest=file_sha256(artifact_target),
    )
    _write_json(output_dir / DEFAULT_BUNDLE_PATH, bundle)
    manifest = _build_manifest(output_dir=output_dir, scope=scope, package_id=f"package:{run.run_id}")
    _write_json(output_dir / "manifest.json", manifest)
    return {"package_path": str(output_dir), "run_id": run.run_id, "compare_scope": scope}


def _build_bundle(
    *,
    run: OutwardRunRecord,
    approvals: list[OutwardApprovalProposal],
    ledger: dict[str, Any],
    workspace_root: Path,
    output_dir: Path,
    scope: str,
    artifact_source: Path,
    artifact_digest: str,
) -> dict[str, Any]:
    approval = approvals[0] if approvals else None
    proposal_event = _first_event(ledger, "proposal_made")
    tool_event = _first_event(ledger, "tool_invoked")
    tool_name = str((tool_event.get("payload") or {}).get("connector_name") or (approval.tool if approval else ""))
    tool_args_digest = str((tool_event.get("payload") or {}).get("args_hash") or (proposal_event.get("payload") or {}).get("tool_args_hash") or "")
    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"bundle:{run.run_id}",
        "run_id": run.run_id,
        "produced_at_iso": "",
        "compare_scope": scope,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier_request": "outward_lab_only",
        "run_authority": _run_authority(run),
        "approval_authority": [_approval_authority(item, tool_args_digest) for item in approvals],
        "ledger_evidence": _ledger_evidence(ledger, output_dir),
        "effect_evidence": [_effect_evidence(run, approval, tool_event, tool_name, tool_args_digest)] if tool_event else [],
        "model_invocation_evidence": [_model_evidence(workspace_root, proposal_event)] if proposal_event else [],
        "policy_identity": _policy_identity(run),
        "artifact_refs": [
            {
                "artifact_role": "committed_output",
                "path": _relative_or_absolute(artifact_source, workspace_root),
                "package_path": DEFAULT_COMMITTED_ARTIFACT_PATH,
                "digest": artifact_digest,
                "classification": "authority",
            }
        ],
        "package_refs": {
            "ledger_export_path": DEFAULT_LEDGER_EXPORT_PATH,
            "committed_output_path": DEFAULT_COMMITTED_ARTIFACT_PATH,
        },
    }


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
    manifest = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "compare_scope": scope,
        "bundle_path": DEFAULT_BUNDLE_PATH,
        "ledger_export_path": DEFAULT_LEDGER_EXPORT_PATH,
        "artifact_paths": {"committed_output": DEFAULT_COMMITTED_ARTIFACT_PATH},
        "file_digests": {
            DEFAULT_BUNDLE_PATH: file_sha256(output_dir / DEFAULT_BUNDLE_PATH),
            DEFAULT_LEDGER_EXPORT_PATH: file_sha256(output_dir / DEFAULT_LEDGER_EXPORT_PATH),
            DEFAULT_COMMITTED_ARTIFACT_PATH: file_sha256(output_dir / DEFAULT_COMMITTED_ARTIFACT_PATH),
        },
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
