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
        "capabilities": {
            "mode": "disabled",
            "decisions": [],
            "denied_count": 0,
            "granted_count": 0,
        },
        "trace": None,
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

    if isinstance(turn_input, dict) and "stage_triplet" in turn_input:
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
