from __future__ import annotations

from typing import Any

from .detectors import dominance_hints


def compute_run_hints(
    *,
    action_histogram: dict[str, int],
    first_agent_id: str,
    win_rates: dict[str, float],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    return dominance_hints(
        action_histogram=action_histogram,
        action_with_alternatives_histogram=action_histogram,
        first_agent_id=first_agent_id,
        win_rates=win_rates,
        thresholds=thresholds,
    )

