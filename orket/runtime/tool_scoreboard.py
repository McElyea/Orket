from __future__ import annotations

from typing import Any

from orket.runtime.protocol_error_codes import (
    E_SCOREBOARD_INCOMPLETE_LEDGER_PREFIX,
    format_protocol_error,
)


def build_tool_scoreboard(
    events: list[dict[str, Any]],
    *,
    scoreboard_policy_version: str = "1.0",
    window_max_invocations: int = 1000,
    window_max_days: int = 30,
) -> dict[str, Any]:
    ordered_events = sorted(
        [dict(row) for row in events if isinstance(row, dict)],
        key=lambda row: int(row.get("event_seq") or row.get("sequence_number") or 0),
    )
    open_calls: dict[int, dict[str, Any]] = {}
    tool_rows: dict[str, dict[str, Any]] = {}

    for event in ordered_events:
        kind = str(event.get("kind") or "").strip()
        event_seq = int(event.get("event_seq") or event.get("sequence_number") or 0)
        if event_seq <= 0:
            continue
        if kind == "tool_call":
            open_calls[event_seq] = dict(event)
            continue
        if kind not in {"tool_result", "operation_result"}:
            continue
        call_sequence_number = int(event.get("call_sequence_number") or 0)
        if call_sequence_number <= 0:
            raise ValueError(_scoreboard_error("call_sequence_number_missing"))
        call_event = open_calls.pop(call_sequence_number, None)
        if call_event is None:
            raise ValueError(_scoreboard_error("tool_result_without_open_call"))
        tool_name = str(call_event.get("tool_name") or event.get("tool_name") or call_event.get("tool") or "").strip()
        if not tool_name:
            raise ValueError(_scoreboard_error("tool_name_missing"))
        result_payload = event.get("result")
        result_payload = result_payload if isinstance(result_payload, dict) else {}
        ok = bool(result_payload.get("ok", False))

        row = tool_rows.get(tool_name)
        if row is None:
            row = {
                "tool": tool_name,
                "invocations": 0,
                "successes": 0,
                "failures": 0,
                "last_event_seq": 0,
            }
            tool_rows[tool_name] = row
        row["invocations"] = int(row["invocations"]) + 1
        if ok:
            row["successes"] = int(row["successes"]) + 1
        else:
            row["failures"] = int(row["failures"]) + 1
        row["last_event_seq"] = max(int(row["last_event_seq"]), event_seq)

    if open_calls:
        raise ValueError(_scoreboard_error("missing_tool_result_event"))

    tools = []
    for tool_name in sorted(tool_rows.keys()):
        row = dict(tool_rows[tool_name])
        invocations = int(row["invocations"])
        successes = int(row["successes"])
        success_rate = float(successes / invocations) if invocations > 0 else 0.0
        row["success_rate"] = success_rate
        tools.append(row)

    return {
        "scoreboard_schema_version": "1.0",
        "scoreboard_policy_version": str(scoreboard_policy_version or "1.0"),
        "window": {
            "max_invocations": max(int(window_max_invocations), 1),
            "max_days": max(int(window_max_days), 1),
        },
        "tools": tools,
    }


def evaluate_promotion_gate(
    *,
    tool_score: dict[str, Any],
    reliability_threshold: float,
    required_replay_runs: int,
    replay_pass_count: int,
    unresolved_drift_count: int,
) -> dict[str, Any]:
    invocations = int(tool_score.get("invocations") or 0)
    success_rate = float(tool_score.get("success_rate") or 0.0)
    threshold = float(reliability_threshold)
    required_replay = max(int(required_replay_runs), 1)
    replay_passes = max(int(replay_pass_count), 0)
    drift_count = max(int(unresolved_drift_count), 0)

    reasons: list[str] = []
    if invocations <= 0:
        reasons.append("insufficient_invocations")
    if success_rate < threshold:
        reasons.append("reliability_threshold_not_met")
    if replay_passes < required_replay:
        reasons.append("replay_parity_not_met")
    if drift_count > 0:
        reasons.append("unresolved_drift_present")

    return {
        "tool": str(tool_score.get("tool") or ""),
        "promotion_gate_policy_version": "1.0",
        "eligible": len(reasons) == 0,
        "reasons": reasons,
        "inputs": {
            "invocations": invocations,
            "success_rate": success_rate,
            "reliability_threshold": threshold,
            "required_replay_runs": required_replay,
            "replay_pass_count": replay_passes,
            "unresolved_drift_count": drift_count,
        },
    }


def _scoreboard_error(detail: str) -> str:
    return format_protocol_error(E_SCOREBOARD_INCOMPLETE_LEDGER_PREFIX, detail)
