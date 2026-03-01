from __future__ import annotations

from typing import Any


def deadlock_anomaly(*, agent_id: str, step_index: int, state_digest: str) -> dict[str, Any]:
    return {
        "type": "deadlock",
        "severity": 4,
        "agent_id": agent_id,
        "step_index": step_index,
        "state_digest": state_digest,
    }


def cycle_anomaly(*, cycle_entry_step: int, cycle_length: int, step_index: int, state_digest: str) -> dict[str, Any]:
    return {
        "type": "cycle_detected",
        "severity": 5,
        "cycle_entry_step": cycle_entry_step,
        "cycle_length": cycle_length,
        "step_index": step_index,
        "state_digest": state_digest,
    }


def illegal_action_anomaly(
    *,
    agent_id: str,
    step_index: int,
    action_key: str,
    attempted_action_cjson: str,
    legal_action_keys: list[str],
) -> dict[str, Any]:
    return {
        "type": "illegal_action_attempt",
        "severity": 3,
        "agent_id": agent_id,
        "step_index": step_index,
        "action_key": action_key,
        "attempted_action_cjson": attempted_action_cjson,
        "legal_action_keys": list(legal_action_keys),
    }


def dominance_hints(
    *,
    action_histogram: dict[str, int],
    action_with_alternatives_histogram: dict[str, int],
    first_agent_id: str,
    win_rates: dict[str, float],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    overuse = float(thresholds.get("dominance_action_pct", 0.9))
    underuse = float(thresholds.get("underuse_action_pct", 0.05))
    first_player_threshold = float(thresholds.get("first_player_win_rate_threshold", 0.7))
    alternative_total = sum(action_with_alternatives_histogram.values())
    if alternative_total > 0:
        for action_key, count in sorted(action_with_alternatives_histogram.items()):
            pct = count / alternative_total
            if pct >= overuse:
                hints.append(
                    {
                        "type": "dominance_hint",
                        "severity": 1,
                        "action_key": action_key,
                        "metric": "overuse",
                        "value": round(pct, 6),
                        "threshold": overuse,
                    }
                )
            if pct <= underuse:
                hints.append(
                    {
                        "type": "dominance_hint",
                        "severity": 1,
                        "action_key": action_key,
                        "metric": "underuse",
                        "value": round(pct, 6),
                        "threshold": underuse,
                    }
                )
    first_rate = float(win_rates.get(first_agent_id, 0.0))
    if first_rate >= first_player_threshold:
        hints.append(
            {
                "type": "first_player_skew",
                "severity": 2,
                "agent_id": first_agent_id,
                "value": round(first_rate, 6),
                "threshold": first_player_threshold,
            }
        )
    return hints


def suspicion_rank(anomaly_type: str) -> int:
    ordering = {
        "cycle_detected": 5,
        "deadlock": 4,
        "illegal_action_attempt": 3,
        "timeout": 2,
        "dominance_hint": 1,
        "first_player_skew": 1,
    }
    return ordering.get(anomaly_type, 0)

