from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def runtime_blocker_rows(
    *,
    entity_id: str,
    scenario_inputs: list[dict[str, Any]],
    locked_budgets: list[int],
    error: Exception,
    triple_variant: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    inspect_rows: list[dict[str, Any]] = []
    compare_rows: list[dict[str, Any]] = []
    error_text = f"{type(error).__name__}: {error}"
    for locked_budget in locked_budgets:
        for scenario_input in scenario_inputs:
            inspect_row = {
                "entity_id": entity_id,
                "scenario_id": str(scenario_input["id"]),
                "locked_budget": int(locked_budget),
                "execution_status": "runtime_blocker",
                "blocking_error": error_text,
                "rounds": [],
            }
            compare_row = {
                "entity_id": entity_id,
                "scenario_id": str(scenario_input["id"]),
                "locked_budget": int(locked_budget),
                "execution_status": "runtime_blocker",
                "converged": False,
                "stop_reason": "RUNTIME_BLOCKER",
                "rounds_consumed": 0,
                "reopened_decision_count": 0,
                "contradiction_count": 0,
                "regression_count": 0,
                "carry_forward_integrity": 0.0,
                "round_latency_ms": [0],
                "round_active_context_size_bytes": [0],
                "round_active_context_size_tokens": [],
                "blocking_error": error_text,
            }
            if triple_variant is None:
                inspect_row["pair_id"] = entity_id
                compare_row["pair_id"] = entity_id
            else:
                reviewer_order = [row["role"] for row in list(triple_variant["reviewer_order"])]
                inspect_row["base_triple_id"] = str(triple_variant["base_triple_id"])
                inspect_row["reviewer_order"] = reviewer_order
                compare_row["base_triple_id"] = str(triple_variant["base_triple_id"])
                compare_row["reviewer_order"] = reviewer_order
            inspect_rows.append(inspect_row)
            compare_rows.append(compare_row)
    return inspect_rows, compare_rows


def load_existing_payload(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def existing_scenario_rows(payload: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get(key)
    return [dict(row) for row in list(rows or []) if isinstance(row, dict)]


def completed_entity_ids(
    scenario_rows: list[dict[str, Any]],
    *,
    scenario_count: int,
    budget_count: int,
) -> set[str]:
    required = int(scenario_count) * int(budget_count)
    counts: dict[str, int] = {}
    for row in scenario_rows:
        entity_id = str(row.get("entity_id") or row.get("pair_id") or "").strip()
        if not entity_id:
            continue
        counts[entity_id] = int(counts.get(entity_id, 0)) + 1
    return {entity_id for entity_id, count in counts.items() if count >= required}


def inventory_status_map(inventory_rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row.get("model_id") or ""), str(row.get("provider") or "")): dict(row)
        for row in inventory_rows
    }
