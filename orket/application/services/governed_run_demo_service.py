from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from functools import partial
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.application.services.governed_run_demo_rendering import (
    render_console_output,
    render_summary,
    render_transcript,
)
from orket.core.domain.governed_run_policy import (
    GovernedRunPolicy,
    classify_action,
    decide_action,
)

DEFAULT_GOVERNED_RUN_SCENARIO = Path(
    str(files("orket.quickstart").joinpath("governed_run_scenario.yaml"))
)
DEFAULT_RUNS_ROOT = Path(".runs")
DEFAULT_STARTED_AT = "2026-07-12T00:00:00Z"
DEFAULT_COMPLETED_AT = "2026-07-12T00:00:01Z"
EVIDENCE_SCHEMA_VERSION = "governed_run.evidence.v1"
REPLAY_SCHEMA_VERSION = "governed_run.replay.v1"


async def run_governed_run_scenario(
    scenario_path: Path = DEFAULT_GOVERNED_RUN_SCENARIO,
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    workspace, = capture_file_roots([workspace_root or Path()])
    scenario_path = Path(scenario_path)
    workspace = await run_owned_thread(workspace.resolve, label="demo-workspace")
    scenario_file = await run_owned_thread(
        partial(_resolve_scenario_path, scenario_path, workspace), label="demo-scenario-path")
    scenario = await _load_scenario(scenario_file)
    policy = GovernedRunPolicy.from_mapping(_dict_value(scenario.get("policy")))
    run_id = _safe_run_id(str(scenario.get("run_id") or scenario.get("name") or "governed-run-demo"))
    started_at = str(scenario.get("started_at") or DEFAULT_STARTED_AT)
    completed_at = str(scenario.get("completed_at") or DEFAULT_COMPLETED_AT)
    actions = _normalize_actions(scenario.get("actions"))
    rows = []

    for action in actions:
        rows.append(await _evaluate_action(action, policy=policy, workspace=workspace))

    evidence = _build_evidence(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        scenario=scenario,
        scenario_file=scenario_file,
        policy=policy,
        actions=rows,
    )
    replay = build_replay_from_evidence(evidence)
    transcript = render_transcript(evidence)
    summary = render_summary(evidence)

    run_dir = workspace / DEFAULT_RUNS_ROOT / run_id
    await _mkdir(run_dir)
    await _write_json(run_dir / "evidence.json", evidence)
    await _write_text(run_dir / "transcript.md", transcript)
    await _write_json(run_dir / "replay.json", replay)
    await _write_text(run_dir / "summary.md", summary)

    return await run_owned_thread(
        partial(_execution_result, run_id, run_dir, workspace, evidence, replay), label="demo-result-paths")


def _execution_result(run_id: str, run_dir: Path, workspace: Path, evidence: dict, replay: dict) -> dict[str, Any]:
    return {
        "kind": "governed_run_execution",
        "ok": True,
        "run_id": run_id,
        "run_dir": _display_path(run_dir, workspace),
        "artifact_paths": {
            "evidence": _display_path(run_dir / "evidence.json", workspace),
            "transcript": _display_path(run_dir / "transcript.md", workspace),
            "replay": _display_path(run_dir / "replay.json", workspace),
            "summary": _display_path(run_dir / "summary.md", workspace),
        },
        "evidence": evidence,
        "replay": replay,
        "console_output": render_console_output(evidence, run_dir=_display_path(run_dir, workspace)),
    }


async def inspect_governed_run_bundle(run_dir: Path) -> dict[str, Any]:
    evidence = await _read_json(run_dir / "evidence.json")
    actions = []
    for action in list(evidence.get("proposed_actions") or []):
        if not isinstance(action, dict):
            continue
        actions.append(
            {
                "action_id": action.get("action_id"),
                "kind": action.get("kind"),
                "risk": _nested(action, "risk_classification", "risk"),
                "decision": _nested(action, "policy_decision", "decision"),
                "status": action.get("resulting_status"),
                "side_effect_occurred": bool(action.get("side_effect_occurred")),
            }
        )
    return {
        "kind": "governed_run_inspection",
        "ok": True,
        "run_id": evidence.get("run_id"),
        "scenario_name": _nested(evidence, "scenario", "name"),
        "status": evidence.get("resulting_status"),
        "started_at": evidence.get("started_at"),
        "completed_at": evidence.get("completed_at"),
        "totals": evidence.get("totals"),
        "actions": actions,
        "artifacts": {
            "evidence": str((run_dir / "evidence.json").as_posix()),
            "transcript": str((run_dir / "transcript.md").as_posix()),
            "replay": str((run_dir / "replay.json").as_posix()),
            "summary": str((run_dir / "summary.md").as_posix()),
        },
    }


async def replay_governed_run_bundle(run_dir: Path) -> dict[str, Any]:
    evidence = await _read_json(run_dir / "evidence.json")
    replay = build_replay_from_evidence(evidence)
    return {
        "kind": "governed_run_replay",
        "ok": replay["replay_status"] == "success",
        "run_id": evidence.get("run_id"),
        "run_dir": str(run_dir.as_posix()),
        **replay,
    }


def is_governed_run_bundle(target: Path) -> bool:
    return target.is_dir() and (target / "evidence.json").is_file()


def build_replay_from_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    policy = GovernedRunPolicy.from_mapping(_dict_value(evidence.get("policy")))
    reconstructed = []
    all_match = True
    for recorded in list(evidence.get("proposed_actions") or []):
        if not isinstance(recorded, Mapping):
            all_match = False
            continue
        proposal = _dict_value(recorded.get("proposal"))
        classification = classify_action(proposal).to_dict()
        decision = decide_action(proposal, policy).to_dict()
        risk_matches = classification == _dict_value(recorded.get("risk_classification"))
        decision_matches = decision == _dict_value(recorded.get("policy_decision"))
        all_match = all_match and risk_matches and decision_matches
        reconstructed.append(
            {
                "action_id": recorded.get("action_id"),
                "risk_classification": classification,
                "policy_decision": decision,
                "risk_matches_evidence": risk_matches,
                "decision_matches_evidence": decision_matches,
                "side_effect_replayed": False,
            }
        )
    return {
        "schema_version": REPLAY_SCHEMA_VERSION,
        "run_id": evidence.get("run_id"),
        "source_evidence_hash": _hash_json(evidence),
        "side_effects_replayed": False,
        "replay_status": "success" if all_match else "failure",
        "reconstructed_actions": reconstructed,
    }


async def _evaluate_action(action: dict[str, Any], *, policy: GovernedRunPolicy, workspace: Path) -> dict[str, Any]:
    classification = classify_action(action)
    decision = decide_action(action, policy)
    row: dict[str, Any] = {
        "action_id": action["action_id"],
        "proposed_by": action["proposed_by"],
        "kind": action["kind"],
        "intent": action["intent"],
        "target": action.get("target", ""),
        "command": action.get("command", ""),
        "proposal": dict(action),
        "risk_classification": classification.to_dict(),
        "policy_decision": decision.to_dict(),
        "approval": _approval_record(decision.to_dict()),
        "side_effect_occurred": False,
    }
    if decision.decision == "allow" and classification.risk == "read_only":
        observation = await run_owned_thread(
            partial(_read_only_observation, workspace, str(action.get("target") or ".")), label="demo-observation")
        row["observation"] = observation
        row["resulting_status"] = "success" if observation.get("status") == "success" else "failure"
    elif decision.decision == "requires_approval":
        row["resulting_status"] = "blocked_pending_approval"
    elif decision.decision == "deny":
        row["resulting_status"] = "blocked"
    else:
        row["resulting_status"] = "allowed_not_executed_by_demo"
    return row


def _build_evidence(
    *,
    run_id: str,
    started_at: str,
    completed_at: str,
    scenario: Mapping[str, Any],
    scenario_file: Path,
    policy: GovernedRunPolicy,
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    totals = {
        "allowed": sum(1 for action in actions if _nested(action, "policy_decision", "decision") == "allow"),
        "requires_approval": sum(
            1 for action in actions if _nested(action, "policy_decision", "decision") == "requires_approval"
        ),
        "denied": sum(1 for action in actions if _nested(action, "policy_decision", "decision") == "deny"),
        "side_effects_occurred": sum(1 for action in actions if bool(action.get("side_effect_occurred"))),
    }
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "scenario": {
            "name": str(scenario.get("name") or ""),
            "path": scenario_file.as_posix(),
            "model": _dict_value(scenario.get("model")),
        },
        "policy": policy.to_dict(),
        "proposed_actions": actions,
        "totals": totals,
        "resulting_status": "completed",
    }


async def _load_scenario(path: Path) -> dict[str, Any]:
    try:
        raw = await run_owned_thread(partial(path.read_text, encoding="utf-8"), label="demo-scenario-read")
    except OSError as exc:
        raise ValueError(f"governed-run scenario not found: {path}") from exc
    payload = yaml.safe_load(raw)
    if not isinstance(payload, dict):
        raise ValueError("governed-run scenario must be a YAML object")
    return payload


def _normalize_actions(raw_actions: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ValueError("governed-run scenario requires at least one action")
    actions = []
    for index, raw in enumerate(raw_actions, start=1):
        if not isinstance(raw, Mapping):
            raise ValueError(f"governed-run action {index} must be an object")
        action = dict(raw)
        action_id = str(action.get("id") or action.get("action_id") or f"action-{index:03d}").strip()
        kind = str(action.get("kind") or action.get("type") or "").strip().lower()
        if not kind:
            raise ValueError(f"governed-run action {action_id} requires kind")
        action["action_id"] = _safe_run_id(action_id)
        action["kind"] = kind
        action["proposed_by"] = str(action.get("proposed_by") or "simulated_model")
        action["intent"] = str(action.get("intent") or action.get("description") or f"Wants to {kind}")
        action["target"] = str(action.get("target") or action.get("path") or "")
        action["command"] = str(action.get("command") or "")
        actions.append(action)
    return actions


def _read_only_observation(workspace: Path, target_raw: str) -> dict[str, Any]:
    root = workspace.resolve()
    target = (root / (target_raw or ".")).resolve()
    if not target.is_relative_to(root):
        return {"status": "blocked", "reason": "read target is outside the workspace", "path": target_raw}
    if target.is_dir():
        entries = sorted(child.relative_to(root).as_posix() for child in target.iterdir())
        return {"status": "success", "type": "directory_listing", "path": target_raw or ".", "entries": entries}
    if target.is_file():
        stat = target.stat()
        return {"status": "success", "type": "file_metadata", "path": target_raw, "size_bytes": stat.st_size}
    return {"status": "failure", "reason": "read target not found", "path": target_raw}


def _approval_record(decision: Mapping[str, Any]) -> dict[str, Any]:
    if bool(decision.get("approval_required")):
        return {
            "required": True,
            "decision": "not_requested",
            "reason": "deterministic demo records the approval gate without executing the side effect",
        }
    return {"required": False, "decision": "not_required"}


def _resolve_scenario_path(path: Path, workspace: Path) -> Path:
    candidate = path if path.is_absolute() else workspace / path
    return candidate.resolve()


async def _mkdir(path: Path) -> None:
    await run_owned_thread(partial(path.mkdir, parents=True, exist_ok=True), label="demo-directory")


async def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    await _write_text(path, json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


async def _write_text(path: Path, content: str) -> None:
    path, = capture_file_roots([path])
    await _mkdir(path.parent)
    await run_owned_thread(partial(path.write_text, content, encoding="utf-8"), label="demo-write")


async def _read_json(path: Path) -> dict[str, Any]:
    path, = capture_file_roots([path])
    raw = await run_owned_thread(partial(path.read_text, encoding="utf-8"), label="demo-read")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path.as_posix()}")
    return payload


def _hash_json(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_run_id(raw: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw).strip()).strip(".-_")
    return token[:96] or "governed-run-demo"


def _display_path(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nested(payload: Mapping[str, Any], outer: str, inner: str) -> Any:
    nested = payload.get(outer)
    return nested.get(inner) if isinstance(nested, Mapping) else None
