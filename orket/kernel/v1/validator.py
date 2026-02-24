from __future__ import annotations

import json
import hashlib
from functools import lru_cache
from pathlib import Path
from uuid import uuid4
from typing import Any

from orket.kernel.v1.canonical import compute_turn_result_digest
from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


CONTRACT_VERSION = "kernel_api/v1"
DEFAULT_VISIBILITY_MODE = "local_only"
DEFAULT_WORKSPACE_ROOT = ".orket_kernel"
DEFAULT_CAPABILITY_POLICY_SOURCE = "policy://orket/kernel/v1/default"
DEFAULT_CAPABILITY_POLICY_VERSION = "v1"
DEFAULT_CAPABILITY_POLICY_PATH = Path("model/core/contracts/kernel_capability_policy_v1.json")


def _issue(*, stage: str, code: str, location: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "level": "FAIL",
        "stage": stage,
        "code": code,
        "location": location,
        "message": message,
        "details": details or {},
    }


def _event(level: str, stage: str, code: str, location: str, message: str) -> str:
    return f"[{level}] [STAGE:{stage}] [CODE:{code}] [LOC:{location}] {message} |"


def _base_turn_result(
    *,
    run_id: str,
    turn_id: str,
    outcome: str,
    stage: str,
    issues: list[dict[str, Any]],
    events: list[str],
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "turn_id": turn_id,
        "outcome": outcome,
        "stage": stage,
        "errors": len([i for i in issues if i.get("level") == "FAIL"]),
        "warnings": 0,
        "issues": issues,
        "events": events,
        "transition": {
            "prior_state_digest": None,
            "proposed_state_digest": "0" * 64,
            "inputs_digest": "0" * 64,
            "diff_summary": {
                "kind": "host_supplied",
                "changed_count": 0,
                "triplet_stems": [],
                "solo_json_paths": [],
            },
            "artifacts": [],
        },
        "capabilities": capabilities
        or {
            "mode": "disabled",
            "decisions": [],
            "decisions_v1_2_1": [],
            "denied_count": 0,
            "granted_count": 0,
        },
        "trace": None,
    }


def _capability_decision(*, subject: str, action: str, resource: str, result: str, reason_code: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "subject": subject,
        "action": action,
        "resource": resource,
        "result": result,
        "reason_code": reason_code,
        "evidence": evidence,
    }


def _capability_decision_record(
    *,
    run_id: str,
    turn_id: str,
    tool_name: str,
    action: str,
    ordinal: int,
    outcome: str,
    deny_code: str | None,
    info_code: str | None,
    reason: str,
    provenance: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "turn_id": turn_id,
        "tool_name": tool_name,
        "action": action,
        "ordinal": ordinal,
        "outcome": outcome,
        "stage": "capability",
        "deny_code": deny_code,
        "info_code": info_code,
        "reason": reason,
        "provenance": provenance,
    }
    decision_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    payload["decision_id"] = decision_id
    return payload


def _capability_evidence(context: dict[str, Any]) -> dict[str, Any]:
    policy = _load_capability_policy()
    source = context.get("policy_source") or policy.get("policy_source") or context.get("policy_ref") or DEFAULT_CAPABILITY_POLICY_SOURCE
    version = context.get("policy_version") or policy.get("policy_version") or DEFAULT_CAPABILITY_POLICY_VERSION
    return {
        "policy_ref": str(context.get("policy_ref", source)),
        "capability_source": str(source),
        "capability_version": str(version),
    }


@lru_cache(maxsize=1)
def _load_capability_policy() -> dict[str, Any]:
    try:
        payload = json.loads(DEFAULT_CAPABILITY_POLICY_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _policy_permissions(role: str, task: str, context: dict[str, Any]) -> list[str]:
    context_permissions = context.get("permissions")
    if isinstance(context_permissions, list):
        return sorted({str(item) for item in context_permissions if str(item)})

    policy = _load_capability_policy()
    role_task_permissions = policy.get("role_task_permissions")
    if not isinstance(role_task_permissions, dict):
        role_task_permissions = {}
    role_permissions = role_task_permissions.get(role)
    if not isinstance(role_permissions, dict):
        role_permissions = {}
    task_permissions = role_permissions.get(task)
    if isinstance(task_permissions, list):
        return sorted({str(item) for item in task_permissions if str(item)})
    default_permissions = policy.get("default_permissions")
    if isinstance(default_permissions, list):
        return sorted({str(item) for item in default_permissions if str(item)})
    return []


def _normalize_turn_digests(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        turn_id = item.get("turn_id")
        turn_digest = item.get("turn_result_digest")
        if not isinstance(turn_id, str) or not turn_id:
            continue
        if not isinstance(turn_digest, str) or len(turn_digest) != 64:
            continue
        entry: dict[str, str] = {"turn_id": turn_id, "turn_result_digest": turn_digest}
        evidence_digest = item.get("evidence_digest")
        if isinstance(evidence_digest, str) and len(evidence_digest) == 64:
            entry["evidence_digest"] = evidence_digest
        out.append(entry)
    return sorted(out, key=lambda item: item["turn_id"])


def _normalize_stage_outcomes(run_payload: dict[str, Any]) -> list[dict[str, str]]:
    items = run_payload.get("stage_outcomes")
    if not isinstance(items, list):
        return []
    out: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        turn_id = item.get("turn_id")
        stage = item.get("stage")
        outcome = item.get("outcome")
        if all(isinstance(v, str) and v for v in (turn_id, stage, outcome)):
            out.append({"turn_id": turn_id, "stage": stage, "outcome": outcome})
    return sorted(out, key=lambda item: item["turn_id"])


def _normalize_issue_codes(run_payload: dict[str, Any]) -> list[dict[str, str]]:
    issues = run_payload.get("issues")
    if not isinstance(issues, list):
        return []
    out: list[dict[str, str]] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        stage = item.get("stage")
        location = item.get("location")
        if all(isinstance(v, str) and v for v in (code, stage, location)):
            out.append({"code": code, "stage": stage, "location": location})
    return sorted(out, key=lambda item: (item["stage"], item["location"], item["code"]))


def _normalize_event_codes(run_payload: dict[str, Any]) -> list[str]:
    events = run_payload.get("events")
    if not isinstance(events, list):
        return []
    out: list[str] = []
    for event in events:
        if not isinstance(event, str):
            continue
        code_marker = "[CODE:"
        start = event.find(code_marker)
        if start < 0:
            continue
        end = event.find("]", start)
        if end <= start:
            continue
        out.append(event[start + len(code_marker) : end])
    return sorted(out)


def _contract_surface(run_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": str(run_payload.get("contract_version", "")),
        "schema_version": str(run_payload.get("schema_version", "")),
        "turn_digests": _normalize_turn_digests(run_payload.get("turn_digests")),
        "stage_outcomes": _normalize_stage_outcomes(run_payload),
        "issue_codes": _normalize_issue_codes(run_payload),
        "event_codes": _normalize_event_codes(run_payload),
    }


def _default_parity(*, run_a: str, run_b: str) -> dict[str, Any]:
    return {
        "kind": "structural_parity",
        "matches": 0,
        "mismatches": 0,
        "expected": {"run_id": run_a, "turn_digests": []},
        "actual": {"run_id": run_b, "turn_digests": []},
    }


def _build_replay_report(
    *,
    mode: str,
    outcome: str,
    issues: list[dict[str, Any]],
    events: list[str],
    parity: dict[str, Any],
    runs_compared: int,
    turns_compared: int,
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": mode,
        "outcome": outcome,
        "runs_compared": runs_compared,
        "turns_compared": turns_compared,
        "issues": issues,
        "events": events,
        "parity": parity,
    }


def start_run_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    workflow_id = request.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise ValueError("workflow_id is required")

    run_id = f"run-{uuid4().hex[:8]}"
    visibility_mode = request.get("visibility_mode") or DEFAULT_VISIBILITY_MODE
    workspace_root = request.get("workspace_root") or DEFAULT_WORKSPACE_ROOT
    return {
        "contract_version": CONTRACT_VERSION,
        "run_handle": {
            "contract_version": CONTRACT_VERSION,
            "run_id": run_id,
            "visibility_mode": visibility_mode,
            "workspace_root": workspace_root,
        },
    }


def execute_turn_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        return _base_turn_result(
            run_id="unknown",
            turn_id=str(request.get("turn_id", "unknown")),
            outcome="FAIL",
            stage="base_shape",
            issues=[
                _issue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/contract_version",
                    message="contract_version must be kernel_api/v1.",
                )
            ],
            events=[
                _event("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/contract_version", "Invalid contract_version.")
            ],
        )

    run_handle = request.get("run_handle")
    turn_id = request.get("turn_id")
    if not isinstance(run_handle, dict):
        return _base_turn_result(
            run_id="unknown",
            turn_id=str(turn_id or "unknown"),
            outcome="FAIL",
            stage="base_shape",
            issues=[
                _issue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/run_handle",
                    message="run_handle must be an object.",
                )
            ],
            events=[_event("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/run_handle", "run_handle missing.")],
        )

    run_id = run_handle.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return _base_turn_result(
            run_id="unknown",
            turn_id=str(turn_id or "unknown"),
            outcome="FAIL",
            stage="base_shape",
            issues=[
                _issue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_MISSING_RUN_ID",
                    location="/run_handle/run_id",
                    message="run_id is required.",
                )
            ],
            events=[_event("FAIL", "base_shape", "E_BASE_SHAPE_MISSING_RUN_ID", "/run_handle/run_id", "run_id missing.")],
        )

    if not isinstance(turn_id, str) or not turn_id:
        return _base_turn_result(
            run_id=run_id,
            turn_id="unknown",
            outcome="FAIL",
            stage="base_shape",
            issues=[
                _issue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/turn_id",
                    message="turn_id is required.",
                )
            ],
            events=[_event("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/turn_id", "turn_id missing.")],
        )

    workspace_root = run_handle.get("workspace_root") or DEFAULT_WORKSPACE_ROOT
    root = Path(str(workspace_root))
    lsi = LocalSovereignIndex(str(root))

    turn_input = request.get("turn_input")
    commit_intent = request.get("commit_intent", "stage_only")

    events: list[str] = []
    issues: list[dict[str, Any]] = []
    stage = "base_shape"
    outcome = "PASS"
    capabilities: dict[str, Any] = {
        "mode": "disabled",
        "decisions": [],
        "decisions_v1_2_1": [],
        "denied_count": 0,
        "granted_count": 0,
    }

    if isinstance(turn_input, dict) and "tool_call" in turn_input:
        context = turn_input.get("context")
        if not isinstance(context, dict):
            context = {}
        tool_call = turn_input.get("tool_call")
        if not isinstance(tool_call, dict):
            tool_call = {}

        capability_enabled = bool(context.get("capability_enforcement", True))
        if not capability_enabled:
            stage = "capability"
            action = str(tool_call.get("action", "tool.call"))
            resource = str(tool_call.get("resource", "unknown"))
            decision_record = _capability_decision_record(
                run_id=run_id,
                turn_id=turn_id,
                tool_name=resource,
                action=action,
                ordinal=0,
                outcome="skipped",
                deny_code=None,
                info_code="I_CAPABILITY_SKIPPED",
                reason="Capability module disabled for this request.",
                provenance=None,
            )
            capabilities["decisions_v1_2_1"] = [decision_record]
            events.append(
                _event("INFO", "capability", "I_CAPABILITY_SKIPPED", "/turn_input/context", "Capability module disabled.")
            )
        else:
            capabilities["mode"] = "enabled"
            subject = str(context.get("subject", "unknown"))
            role = str(context.get("role", ""))
            task = str(context.get("task", ""))
            action = str(tool_call.get("action", "tool.call"))
            resource = str(tool_call.get("resource", "unknown"))
            requested = tool_call.get("requested_permissions")
            declared = tool_call.get("declared_permissions")
            side_effects_declared = bool(tool_call.get("side_effects_declared", True))
            evidence = _capability_evidence(context)
            allowed_permissions = _policy_permissions(role=role, task=task, context=context)

            if not bool(context.get("capability_resolved", True)):
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_CAPABILITY_NOT_RESOLVED",
                    evidence=evidence,
                )
            elif not side_effects_declared:
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_SIDE_EFFECT_UNDECLARED",
                    evidence=evidence,
                )
            elif isinstance(requested, list) and isinstance(declared, list) and not set(requested).issubset(set(declared)):
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_PERMISSION_DENIED",
                    evidence=evidence,
                )
            elif bool(context.get("allow_tool_call", False)) or action in allowed_permissions:
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="GRANT",
                    reason_code="I_GATEKEEPER_PASS",
                    evidence=evidence,
                )
            else:
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_CAPABILITY_DENIED",
                    evidence=evidence,
                )

            capabilities["decisions"] = [decision]
            if decision["result"] == "DENY":
                record_outcome = "unresolved" if decision["reason_code"] == "E_CAPABILITY_NOT_RESOLVED" else "denied"
                record_deny_code = decision["reason_code"]
                record_info_code = None
                record_provenance = None
            else:
                record_outcome = "allowed"
                record_deny_code = None
                record_info_code = None
                record_provenance = evidence
            decision_record = _capability_decision_record(
                run_id=run_id,
                turn_id=turn_id,
                tool_name=resource,
                action=action,
                ordinal=0,
                outcome=record_outcome,
                deny_code=record_deny_code,
                info_code=record_info_code,
                reason=f"Capability decision outcome: {record_outcome}.",
                provenance=record_provenance,
            )
            capabilities["decisions_v1_2_1"] = [decision_record]
            if decision["result"] == "DENY":
                capabilities["denied_count"] = 1
                outcome = "FAIL"
                stage = "capability"
                issues.append(
                    _issue(
                        stage="capability",
                        code=decision["reason_code"],
                        location=f"/capabilities/decisions_v1_2_1/{decision_record['ordinal']}",
                        message="Capability policy denied tool execution.",
                        details={"decision": decision, "decision_record": decision_record},
                    )
                )
                events.append(
                    _event(
                        "FAIL",
                        "capability",
                        decision["reason_code"],
                        f"/capabilities/decisions_v1_2_1/{decision_record['ordinal']}",
                        "Tool execution denied by capability policy.",
                    )
                )
            else:
                capabilities["granted_count"] = 1
                stage = "capability"
                events.append(
                    _event(
                        "INFO",
                        "capability",
                        decision["reason_code"],
                        "/turn_input/tool_call",
                        "Tool execution authorized by capability policy.",
                    )
                )

    if outcome == "PASS" and isinstance(turn_input, dict) and "stage_triplet" in turn_input:
        triplet = turn_input.get("stage_triplet")
        if not isinstance(triplet, dict):
            issues.append(
                _issue(
                    stage="base_shape",
                    code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                    location="/turn_input/stage_triplet",
                    message="stage_triplet must be an object.",
                )
            )
            events.append(
                _event("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/turn_input/stage_triplet", "stage_triplet invalid.")
            )
            outcome = "FAIL"
            stage = "base_shape"
        else:
            stem = triplet.get("stem")
            body = triplet.get("body")
            links = triplet.get("links")
            manifest = triplet.get("manifest", {})
            if not isinstance(stem, str) or not isinstance(body, dict) or not isinstance(links, dict) or not isinstance(manifest, dict):
                issues.append(
                    _issue(
                        stage="base_shape",
                        code="E_BASE_SHAPE_INVALID_MANIFEST_VALUE",
                        location="/turn_input/stage_triplet",
                        message="stage_triplet requires stem/body/links/manifest shapes.",
                    )
                )
                events.append(
                    _event("FAIL", "base_shape", "E_BASE_SHAPE_INVALID_MANIFEST_VALUE", "/turn_input/stage_triplet", "stage_triplet shape invalid.")
                )
                outcome = "FAIL"
                stage = "base_shape"
            else:
                lsi.stage_triplet(
                    run_id=run_id,
                    turn_id=turn_id,
                    stem=stem,
                    body=body,
                    links=links,
                    manifest=manifest,
                )
                stage = "lsi"
                events.append(_event("INFO", "lsi", "I_GATEKEEPER_PASS", "/turn_input/stage_triplet", "Triplet staged."))

    if outcome == "PASS" and commit_intent == "stage_and_request_promotion":
        promotion = promote_turn(root=str(root), run_id=run_id, turn_id=turn_id)
        events.extend(promotion.events)
        issues.extend(
            [
                _issue(
                    stage=i.stage,
                    code=i.code,
                    location=i.location,
                    message=i.message,
                    details=i.details,
                )
                for i in promotion.issues
            ]
        )
        outcome = promotion.outcome
        stage = "promotion"

    result = _base_turn_result(
        run_id=run_id,
        turn_id=turn_id,
        outcome=outcome,
        stage=stage,
        issues=issues,
        events=events,
        capabilities=capabilities,
    )
    result["turn_result_digest"] = compute_turn_result_digest(result)
    return result


def finish_run_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    run_handle = request.get("run_handle")
    if not isinstance(run_handle, dict):
        raise ValueError("run_handle must be an object")
    run_id = run_handle.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("run_handle.run_id is required")
    outcome = request.get("outcome")
    if outcome not in {"PASS", "FAIL"}:
        raise ValueError("outcome must be PASS or FAIL")

    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "outcome": outcome,
        "turns_executed": 0,
        "events": [],
    }


def resolve_capability_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    role = request.get("role")
    task = request.get("task")
    if not isinstance(role, str) or not role:
        raise ValueError("role is required")
    if not isinstance(task, str) or not task:
        raise ValueError("task is required")

    context = request.get("context")
    if not isinstance(context, dict):
        context = {}

    enabled = bool(context.get("capability_enforcement", True))
    evidence = _capability_evidence(context)
    if not enabled:
        return {
            "contract_version": CONTRACT_VERSION,
            "capability_plan": {
                "mode": "disabled",
                "role": role,
                "task": task,
                "permissions": [],
                "policy_source": evidence["capability_source"],
                "policy_version": evidence["capability_version"],
            },
            "events": [_event("INFO", "capability", "I_CAPABILITY_SKIPPED", "/context", "Capability module disabled.")],
        }
    permissions = _policy_permissions(role=role, task=task, context=context)
    return {
        "contract_version": CONTRACT_VERSION,
        "capability_plan": {
            "mode": "enabled",
            "role": role,
            "task": task,
            "permissions": permissions,
            "policy_source": evidence["capability_source"],
            "policy_version": evidence["capability_version"],
        },
        "events": [_event("INFO", "capability", "I_GATEKEEPER_PASS", "/context", "Capability resolved.")],
    }


def authorize_tool_call_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    context = request.get("context")
    tool_request = request.get("tool_request")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if not isinstance(tool_request, dict):
        raise ValueError("tool_request must be an object")

    subject = str(context.get("subject", "unknown"))
    action = str(tool_request.get("action", "tool.call"))
    resource = str(tool_request.get("resource", "unknown"))
    evidence = _capability_evidence(context)
    allowed_permissions = _policy_permissions(
        role=str(context.get("role", "")),
        task=str(context.get("task", "")),
        context=context,
    )

    if not bool(context.get("capability_enforcement", True)):
        decision = _capability_decision(
            subject=subject,
            action=action,
            resource=resource,
            result="GRANT",
            reason_code="I_CAPABILITY_SKIPPED",
            evidence=evidence,
        )
        return {"contract_version": CONTRACT_VERSION, "decision": decision}

    requested = tool_request.get("requested_permissions")
    declared = tool_request.get("declared_permissions")
    side_effects_declared = bool(tool_request.get("side_effects_declared", True))

    if not bool(context.get("capability_resolved", True)):
        reason_code = "E_CAPABILITY_NOT_RESOLVED"
        result = "DENY"
    elif not side_effects_declared:
        reason_code = "E_SIDE_EFFECT_UNDECLARED"
        result = "DENY"
    elif isinstance(requested, list) and isinstance(declared, list) and not set(requested).issubset(set(declared)):
        reason_code = "E_PERMISSION_DENIED"
        result = "DENY"
    elif bool(context.get("allow_tool_call", False)) or action in allowed_permissions:
        reason_code = "I_GATEKEEPER_PASS"
        result = "GRANT"
    else:
        reason_code = "E_CAPABILITY_DENIED"
        result = "DENY"

    decision = _capability_decision(
        subject=subject,
        action=action,
        resource=resource,
        result=result,
        reason_code=reason_code,
        evidence=evidence,
    )
    return {"contract_version": CONTRACT_VERSION, "decision": decision}


def replay_run_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    descriptor = request.get("run_descriptor")
    if not isinstance(descriptor, dict):
        descriptor = {}

    required = [
        "run_id",
        "workflow_id",
        "contract_version",
        "schema_version",
        "policy_profile_ref",
        "model_profile_ref",
        "runtime_profile_ref",
        "trace_ref",
        "state_ref",
    ]
    missing = [field for field in required if not isinstance(descriptor.get(field), str) or not descriptor.get(field)]
    run_id = str(descriptor.get("run_id", "unknown"))
    parity = _default_parity(run_a=run_id, run_b=run_id)

    if missing:
        issue = _issue(
            stage="replay",
            code="E_REPLAY_INPUT_MISSING",
            location=f"/run_descriptor/{missing[0]}",
            message="Replay input descriptor is incomplete.",
            details={"missing_fields": missing},
        )
        return _build_replay_report(
            mode="replay_run",
            outcome="FAIL",
            issues=[issue],
            events=[_event("FAIL", "replay", "E_REPLAY_INPUT_MISSING", f"/run_descriptor/{missing[0]}", "Replay input missing.")],
            parity=parity,
            runs_compared=1,
            turns_compared=0,
        )

    if descriptor.get("contract_version") != CONTRACT_VERSION:
        issue = _issue(
            stage="replay",
            code="E_REPLAY_VERSION_MISMATCH",
            location="/run_descriptor/contract_version",
            message="Replay descriptor contract_version mismatch.",
            details={"expected": CONTRACT_VERSION, "actual": descriptor.get("contract_version")},
        )
        return _build_replay_report(
            mode="replay_run",
            outcome="FAIL",
            issues=[issue],
            events=[
                _event(
                    "FAIL",
                    "replay",
                    "E_REPLAY_VERSION_MISMATCH",
                    "/run_descriptor/contract_version",
                    "Replay version mismatch.",
                )
            ],
            parity=parity,
            runs_compared=1,
            turns_compared=0,
        )

    return _build_replay_report(
        mode="replay_run",
        outcome="PASS",
        issues=[],
        events=[_event("INFO", "replay", "I_GATEKEEPER_PASS", "/run_descriptor", "Replay input accepted.")],
        parity=parity,
        runs_compared=1,
        turns_compared=0,
    )


def compare_runs_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    run_a = request.get("run_a")
    run_b = request.get("run_b")
    if not isinstance(run_a, dict) or not isinstance(run_b, dict):
        issue = _issue(
            stage="replay",
            code="E_REPLAY_INPUT_MISSING",
            location="/run_a",
            message="compare_runs requires run_a and run_b objects.",
            details={},
        )
        return _build_replay_report(
            mode="compare_runs",
            outcome="FAIL",
            issues=[issue],
            events=[_event("FAIL", "replay", "E_REPLAY_INPUT_MISSING", "/run_a", "compare_runs input missing.")],
            parity=_default_parity(run_a="unknown", run_b="unknown"),
            runs_compared=2,
            turns_compared=0,
        )

    run_a_id = str(run_a.get("run_id", "run-a"))
    run_b_id = str(run_b.get("run_id", "run-b"))
    parity = _default_parity(run_a=run_a_id, run_b=run_b_id)
    surface_a = _contract_surface(run_a)
    surface_b = _contract_surface(run_b)
    sorted_a = surface_a["turn_digests"]
    sorted_b = surface_b["turn_digests"]
    parity["expected"]["turn_digests"] = sorted_a
    parity["actual"]["turn_digests"] = sorted_b
    comparisons = {
        "turn_digests": sorted_a == sorted_b,
        "stage_outcomes": surface_a["stage_outcomes"] == surface_b["stage_outcomes"],
        "issue_codes": surface_a["issue_codes"] == surface_b["issue_codes"],
        "event_codes": surface_a["event_codes"] == surface_b["event_codes"],
        "contract_version": surface_a["contract_version"] == surface_b["contract_version"],
        "schema_version": surface_a["schema_version"] == surface_b["schema_version"],
    }
    parity["matches"] = sum(1 for value in comparisons.values() if value)
    parity["mismatches"] = len(comparisons) - parity["matches"]

    if parity["mismatches"] > 0:
        mismatch_fields = sorted([field for field, matched in comparisons.items() if not matched])
        issue = _issue(
            stage="replay",
            code="E_REPLAY_EQUIVALENCE_FAILED",
            location="/run_a/turn_digests",
            message="Run parity mismatch.",
            details={
                "matches": parity["matches"],
                "mismatches": parity["mismatches"],
                "mismatch_fields": mismatch_fields,
            },
        )
        return _build_replay_report(
            mode="compare_runs",
            outcome="FAIL",
            issues=[issue],
            events=[_event("FAIL", "replay", "E_REPLAY_EQUIVALENCE_FAILED", "/run_a/turn_digests", "Replay equivalence failed.")],
            parity=parity,
            runs_compared=2,
            turns_compared=max(len(surface_a["stage_outcomes"]), len(surface_b["stage_outcomes"]), len(sorted_a), len(sorted_b)),
        )

    return _build_replay_report(
        mode="compare_runs",
        outcome="PASS",
        issues=[],
        events=[_event("INFO", "replay", "I_GATEKEEPER_PASS", "/run_a/turn_digests", "Replay equivalence passed.")],
        parity=parity,
        runs_compared=2,
        turns_compared=len(sorted_a),
    )
