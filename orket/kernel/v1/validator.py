from __future__ import annotations

from pathlib import Path
from uuid import uuid4
from typing import Any

from orket.kernel.v1.state.lsi import LocalSovereignIndex
from orket.kernel.v1.state.promotion import promote_turn


CONTRACT_VERSION = "kernel_api/v1"
DEFAULT_VISIBILITY_MODE = "local_only"
DEFAULT_WORKSPACE_ROOT = ".orket_kernel"


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
            events.append(
                _event("INFO", "capability", "I_CAPABILITY_SKIPPED", "/turn_input/context", "Capability module disabled.")
            )
        else:
            capabilities["mode"] = "enabled"
            subject = str(context.get("subject", "unknown"))
            action = str(tool_call.get("action", "tool.call"))
            resource = str(tool_call.get("resource", "unknown"))
            requested = tool_call.get("requested_permissions")
            declared = tool_call.get("declared_permissions")
            side_effects_declared = bool(tool_call.get("side_effects_declared", True))

            if not bool(context.get("capability_resolved", True)):
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_CAPABILITY_NOT_RESOLVED",
                    evidence={"policy_ref": context.get("policy_ref", "unknown")},
                )
            elif not side_effects_declared:
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_SIDE_EFFECT_UNDECLARED",
                    evidence={"policy_ref": context.get("policy_ref", "unknown")},
                )
            elif isinstance(requested, list) and isinstance(declared, list) and not set(requested).issubset(set(declared)):
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_PERMISSION_DENIED",
                    evidence={"policy_ref": context.get("policy_ref", "unknown")},
                )
            elif bool(context.get("allow_tool_call", False)):
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="GRANT",
                    reason_code="I_GATEKEEPER_PASS",
                    evidence={"policy_ref": context.get("policy_ref", "unknown")},
                )
            else:
                decision = _capability_decision(
                    subject=subject,
                    action=action,
                    resource=resource,
                    result="DENY",
                    reason_code="E_CAPABILITY_DENIED",
                    evidence={"policy_ref": context.get("policy_ref", "unknown")},
                )

            capabilities["decisions"] = [decision]
            if decision["result"] == "DENY":
                capabilities["denied_count"] = 1
                outcome = "FAIL"
                stage = "capability"
                issues.append(
                    _issue(
                        stage="capability",
                        code=decision["reason_code"],
                        location="/turn_input/tool_call",
                        message="Capability policy denied tool execution.",
                        details={"decision": decision},
                    )
                )
                events.append(
                    _event(
                        "FAIL",
                        "capability",
                        decision["reason_code"],
                        "/turn_input/tool_call",
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

    return _base_turn_result(
        run_id=run_id,
        turn_id=turn_id,
        outcome=outcome,
        stage=stage,
        issues=issues,
        events=events,
        capabilities=capabilities,
    )


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
    if not enabled:
        return {
            "contract_version": CONTRACT_VERSION,
            "capability_plan": {"mode": "disabled", "role": role, "task": task, "permissions": []},
            "events": [_event("INFO", "capability", "I_CAPABILITY_SKIPPED", "/context", "Capability module disabled.")],
        }

    permissions = context.get("permissions")
    if not isinstance(permissions, list):
        permissions = []
    permissions = sorted(str(item) for item in permissions)
    return {
        "contract_version": CONTRACT_VERSION,
        "capability_plan": {"mode": "enabled", "role": role, "task": task, "permissions": permissions},
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

    if not bool(context.get("capability_enforcement", True)):
        decision = _capability_decision(
            subject=subject,
            action=action,
            resource=resource,
            result="GRANT",
            reason_code="I_CAPABILITY_SKIPPED",
            evidence={"policy_ref": context.get("policy_ref", "unknown")},
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
    elif bool(context.get("allow_tool_call", False)):
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
        evidence={"policy_ref": context.get("policy_ref", "unknown")},
    )
    return {"contract_version": CONTRACT_VERSION, "decision": decision}


def replay_run_v1(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    descriptor = request.get("run_descriptor")
    if not isinstance(descriptor, dict):
        descriptor = {}

    required = ["run_id", "workflow_id", "contract_version", "schema_version"]
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

    digests_a = run_a.get("turn_digests")
    digests_b = run_b.get("turn_digests")
    if not isinstance(digests_a, list):
        digests_a = []
    if not isinstance(digests_b, list):
        digests_b = []

    sorted_a = sorted(digests_a, key=lambda item: str(item.get("turn_id", "")))
    sorted_b = sorted(digests_b, key=lambda item: str(item.get("turn_id", "")))
    parity["expected"]["turn_digests"] = sorted_a
    parity["actual"]["turn_digests"] = sorted_b
    parity["matches"] = sum(1 for left, right in zip(sorted_a, sorted_b) if left == right)
    parity["mismatches"] = abs(len(sorted_a) - len(sorted_b)) + sum(1 for left, right in zip(sorted_a, sorted_b) if left != right)

    if sorted_a != sorted_b:
        issue = _issue(
            stage="replay",
            code="E_REPLAY_EQUIVALENCE_FAILED",
            location="/run_a/turn_digests",
            message="Run parity mismatch.",
            details={"matches": parity["matches"], "mismatches": parity["mismatches"]},
        )
        return _build_replay_report(
            mode="compare_runs",
            outcome="FAIL",
            issues=[issue],
            events=[_event("FAIL", "replay", "E_REPLAY_EQUIVALENCE_FAILED", "/run_a/turn_digests", "Replay equivalence failed.")],
            parity=parity,
            runs_compared=2,
            turns_compared=max(len(sorted_a), len(sorted_b)),
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
