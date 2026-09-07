from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def render_console_output(evidence: Mapping[str, Any], *, run_dir: str) -> str:
    lines = list(_transcript_step_lines(evidence))
    totals = _dict_value(evidence.get("totals"))
    lines.append(
        "[orket] Run completed: "
        f"allowed={totals.get('allowed', 0)} "
        f"approval_required={totals.get('requires_approval', 0)} "
        f"blocked={totals.get('denied', 0)}"
    )
    lines.append(f"[orket] Evidence bundle: {run_dir}")
    lines.append(f"[orket] Inspect: orket inspect {run_dir}")
    lines.append(f"[orket] Replay: orket replay {run_dir}")
    return "\n".join(lines)


def render_transcript(evidence: Mapping[str, Any]) -> str:
    lines = [
        "# Governed Run Transcript",
        "",
        f"- run_id: {evidence.get('run_id')}",
        f"- scenario: {_nested(evidence, 'scenario', 'name')}",
        "",
    ]
    lines.extend(_transcript_step_lines(evidence))
    lines.append("")
    lines.append(f"[orket] Run completed with status: {evidence.get('resulting_status')}")
    return "\n".join(lines) + "\n"


def render_summary(evidence: Mapping[str, Any]) -> str:
    totals = _dict_value(evidence.get("totals"))
    lines = [
        "# Governed Run Summary",
        "",
        f"- run_id: {evidence.get('run_id')}",
        f"- scenario: {_nested(evidence, 'scenario', 'name')}",
        f"- status: {evidence.get('resulting_status')}",
        f"- allowed actions: {totals.get('allowed', 0)}",
        f"- approval-required actions: {totals.get('requires_approval', 0)}",
        f"- denied actions: {totals.get('denied', 0)}",
        f"- side effects occurred: {totals.get('side_effects_occurred', 0)}",
        "",
        "Replay reconstructs policy decisions from `evidence.json` and does not rerun side effects.",
    ]
    return "\n".join(lines) + "\n"


def render_inspection(result: Mapping[str, Any]) -> str:
    lines = [
        f"run_id: {result.get('run_id')}",
        f"scenario: {result.get('scenario_name')}",
        f"status: {result.get('status')}",
        f"started_at: {result.get('started_at')}",
        f"completed_at: {result.get('completed_at')}",
        "actions:",
    ]
    for action in list(result.get("actions") or []):
        if isinstance(action, Mapping):
            lines.append(
                f"- {action.get('action_id')}: "
                f"risk={action.get('risk')} decision={action.get('decision')} status={action.get('status')}"
            )
    artifacts = _dict_value(result.get("artifacts"))
    lines.append(f"evidence: {artifacts.get('evidence')}")
    lines.append(f"replay: {artifacts.get('replay')}")
    return "\n".join(lines)


def render_replay(result: Mapping[str, Any]) -> str:
    lines = [
        f"run_id: {result.get('run_id')}",
        f"replay_status: {result.get('replay_status')}",
        f"source_evidence_hash: {result.get('source_evidence_hash')}",
        f"side_effects_replayed: {str(result.get('side_effects_replayed')).lower()}",
        "reconstructed decisions:",
    ]
    for action in list(result.get("reconstructed_actions") or []):
        if not isinstance(action, Mapping):
            continue
        decision = _nested(action, "policy_decision", "decision")
        risk = _nested(action, "risk_classification", "risk")
        lines.append(f"- {action.get('action_id')}: risk={risk} decision={decision}")
    return "\n".join(lines)


def _transcript_step_lines(evidence: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for action in list(evidence.get("proposed_actions") or []):
        if not isinstance(action, Mapping):
            continue
        lines.append(f"[model] {action.get('intent')}")
        decision = _nested(action, "policy_decision", "decision")
        reason = _nested(action, "policy_decision", "reason")
        if decision == "allow":
            lines.append(f"[orket] Allowed: {reason}")
        elif decision == "requires_approval":
            lines.append(f"[orket] Approval required: {reason}")
        else:
            lines.append(f"[orket] Blocked: {reason}")
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nested(payload: Mapping[str, Any], outer: str, inner: str) -> Any:
    nested = payload.get(outer)
    return nested.get(inner) if isinstance(nested, Mapping) else None
