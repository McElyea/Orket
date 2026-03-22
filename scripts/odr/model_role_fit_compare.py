from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import median
from typing import Any

from scripts.odr.model_role_fit_lane import (
    PairSpec,
    build_entity_budget_aggregate,
    build_entity_summary_aggregate,
)


def _normalize_scenario_run(
    raw: dict[str, Any],
    *,
    structural_stop_reasons: set[str],
) -> dict[str, Any]:
    latency_samples = [float(value) for value in list(raw.get("round_latency_ms") or [])]
    if not latency_samples and raw.get("median_round_latency_ms") is not None:
        latency_samples = [float(raw["median_round_latency_ms"])]
    byte_samples = [float(value) for value in list(raw.get("round_active_context_size_bytes") or [])]
    if not byte_samples and raw.get("median_round_active_context_size_bytes") is not None:
        byte_samples = [float(raw["median_round_active_context_size_bytes"])]
    token_samples = [float(value) for value in list(raw.get("round_active_context_size_tokens") or [])]
    if not token_samples and raw.get("median_round_active_context_size_tokens") is not None:
        token_samples = [float(raw["median_round_active_context_size_tokens"])]
    if not latency_samples or not byte_samples:
        raise ValueError("Scenario run rows must declare latency and active-context byte samples or medians.")
    token_value = raw.get("median_round_active_context_size_tokens")
    stop_reason = str(raw.get("stop_reason") or "NONE").strip() or "NONE"
    return {
        "entity_id": str(raw["entity_id"]),
        "scenario_id": str(raw["scenario_id"]),
        "locked_budget": int(raw["locked_budget"]),
        "execution_status": str(raw.get("execution_status") or "success"),
        "converged": bool(raw["converged"]),
        "stop_reason": stop_reason,
        "rounds_consumed": int(raw["rounds_consumed"]),
        "reopened_decision_count": int(raw["reopened_decision_count"]),
        "contradiction_count": int(raw["contradiction_count"]),
        "regression_count": int(raw["regression_count"]),
        "carry_forward_integrity": float(raw["carry_forward_integrity"]),
        "median_round_latency_ms": float(median(latency_samples)),
        "median_round_active_context_size_bytes": float(median(byte_samples)),
        "median_round_active_context_size_tokens": (
            float(median(token_samples))
            if token_samples
            else float(token_value)
            if token_value is not None
            else None
        ),
        "structural_failure": stop_reason in structural_stop_reasons,
    }


def _sort_key(summary: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(summary["convergence_rate"]),
        float(summary["contradiction_rate"]),
        float(summary["reopened_decision_rate"]),
        float(summary["regression_rate"]),
        float(summary["median_round_latency_ms"]),
        float(summary["median_round_active_context_size_bytes"]),
        -float(summary["carry_forward_integrity"]),
        str(summary["entity_id"]),
    )


def _build_rankings(
    entity_summaries: list[dict[str, Any]],
    *,
    max_structural_failure_rate: float,
    top_entity_count: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    sorted_rows = sorted(entity_summaries, key=_sort_key)
    rankings: list[dict[str, Any]] = []
    surviving_ids: list[str] = []
    next_rank = 1
    for row in sorted_rows:
        execution_blocked = float(row.get("execution_blocker_rate") or 0.0) > 0.0
        structurally_disqualified = float(row["structural_failure_rate"]) > float(max_structural_failure_rate)
        ranking_row = {
            "entity_id": str(row["entity_id"]),
            "rank": None if structurally_disqualified or execution_blocked else next_rank,
            "execution_blocked": execution_blocked,
            "execution_blocker_rate": float(row.get("execution_blocker_rate") or 0.0),
            "structurally_disqualified": structurally_disqualified,
            "structural_failure_rate": float(row["structural_failure_rate"]),
            "convergence_rate": float(row["convergence_rate"]),
            "contradiction_rate": float(row["contradiction_rate"]),
            "reopened_decision_rate": float(row["reopened_decision_rate"]),
            "regression_rate": float(row["regression_rate"]),
            "median_round_latency_ms": float(row["median_round_latency_ms"]),
            "median_round_active_context_size_bytes": float(row["median_round_active_context_size_bytes"]),
            "carry_forward_integrity": float(row["carry_forward_integrity"]),
        }
        if execution_blocked:
            ranking_row["selection_status"] = "execution_blocked"
        elif structurally_disqualified:
            ranking_row["selection_status"] = "structurally_disqualified"
        else:
            ranking_row["selection_status"] = "eligible"
            surviving_ids.append(str(row["entity_id"]))
            next_rank += 1
        rankings.append(ranking_row)
    return rankings, surviving_ids[: int(top_entity_count)]


def _pair_id_to_models(registry: dict[str, Any]) -> dict[str, PairSpec]:
    return {pair.pair_id: pair for pair in registry["primary_pairs"]}


def build_pair_compare_payload(
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    raw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    structural_stop_reasons = set(config["structural_disqualification"]["stop_reasons"])
    deduped_rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for raw in raw_rows:
        normalized = _normalize_scenario_run(raw, structural_stop_reasons=structural_stop_reasons)
        deduped_rows[(str(normalized["entity_id"]), str(normalized["scenario_id"]), int(normalized["locked_budget"]))] = normalized
    scenario_runs = [deduped_rows[key] for key in sorted(deduped_rows)]
    by_pair_budget: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scenario_runs:
        by_pair_budget[(str(row["entity_id"]), int(row["locked_budget"]))].append(row)
        by_pair[str(row["entity_id"])].append(row)

    pair_budget_aggregates = [
        build_entity_budget_aggregate(rows, entity_id=pair_id, locked_budget=locked_budget)
        for (pair_id, locked_budget), rows in sorted(by_pair_budget.items())
    ]
    pair_summary_aggregates = [
        build_entity_summary_aggregate(rows, entity_id=pair_id)
        for pair_id, rows in sorted(by_pair.items())
    ]
    pair_rankings, top_pairs = _build_rankings(
        pair_summary_aggregates,
        max_structural_failure_rate=float(config["structural_disqualification"]["max_failure_rate"]),
        top_entity_count=int(config["top_pair_count_for_triples"]),
    )
    pair_lookup = _pair_id_to_models(registry)
    admitted_models = {
        pair_lookup[pair_id].architect_model
        for pair_id in top_pairs
        if pair_id in pair_lookup
    } | {
        pair_lookup[pair_id].reviewer_model
        for pair_id in top_pairs
        if pair_id in pair_lookup
    }
    return {
        "schema_version": "odr.model_role_fit.pair_compare.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "continuity_mode": str(config["continuity_mode"]),
        "scenario_set": dict(config["scenario_set"]),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "continuity_mode": str(config["continuity_mode"]),
            "locked_budgets": list(config["locked_budgets"]),
            "scenario_set": dict(config["scenario_set"]),
            "structural_disqualification": dict(config["structural_disqualification"]),
            "top_pair_count_for_triples": int(config["top_pair_count_for_triples"]),
        },
        "scenario_runs": scenario_runs,
        "pair_budget_aggregates": pair_budget_aggregates,
        "pair_summary_aggregates": pair_summary_aggregates,
        "pair_rankings": pair_rankings,
        "top_pairs_for_triples": top_pairs,
        "top_models_for_triples": sorted(admitted_models),
    }


def build_pair_verdict_payload(
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    pair_compare_payload: dict[str, Any],
) -> dict[str, Any]:
    ranking_rows = list(pair_compare_payload["pair_rankings"])
    best_pair = next(
        (
            row
            for row in ranking_rows
            if not bool(row["structurally_disqualified"]) and not bool(row.get("execution_blocked"))
        ),
        None,
    )
    selected_pairs = list(pair_compare_payload["top_pairs_for_triples"])
    pair_lookup = _pair_id_to_models(registry)
    pair_verdicts = []
    for row in ranking_rows:
        pair_id = str(row["entity_id"])
        verdict = "eligible_not_selected"
        if bool(row.get("execution_blocked")):
            verdict = "execution_blocked"
        elif bool(row["structurally_disqualified"]):
            verdict = "structurally_disqualified"
        if best_pair and pair_id == str(best_pair["entity_id"]):
            verdict = "best_observed_pair"
        elif pair_id in selected_pairs:
            verdict = "selected_for_triples"
        pair_verdicts.append(
            {
                "pair_id": pair_id,
                "verdict": verdict,
                "rank": row["rank"],
                "pair_spec": pair_lookup[pair_id].as_dict() if pair_id in pair_lookup else None,
                "metrics": {
                    key: row[key]
                    for key in (
                        "convergence_rate",
                        "contradiction_rate",
                        "reopened_decision_rate",
                        "regression_rate",
                        "median_round_latency_ms",
                        "median_round_active_context_size_bytes",
                        "carry_forward_integrity",
                        "execution_blocker_rate",
                        "structural_failure_rate",
                    )
                },
            }
        )
    preferred_triples = list(registry.get("preferred_triples") or [])
    if not preferred_triples:
        triple_phase_status = "not_configured"
        triple_phase_skip_reason = "no_preferred_triples_configured"
    elif len(selected_pairs) < 2:
        triple_phase_status = "skipped_insufficient_survivors"
        triple_phase_skip_reason = "fewer_than_two_non_disqualified_pairs"
    else:
        triple_phase_status = "admitted"
        triple_phase_skip_reason = None
    return {
        "schema_version": "odr.model_role_fit.pair_verdict.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "continuity_mode": str(config["continuity_mode"]),
        },
        "best_observed_pair": str(best_pair["entity_id"]) if best_pair else None,
        "selected_pairs_for_triples": selected_pairs,
        "triple_phase_status": triple_phase_status,
        "triple_phase_skip_reason": triple_phase_skip_reason,
        "pair_verdicts": pair_verdicts,
    }


def build_triple_compare_payload(
    *,
    config: dict[str, Any],
    raw_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    structural_stop_reasons = set(config["structural_disqualification"]["stop_reasons"])
    deduped_rows: dict[tuple[str, str, int], dict[str, Any]] = {}
    for raw in raw_rows:
        normalized = _normalize_scenario_run(raw, structural_stop_reasons=structural_stop_reasons)
        deduped_rows[(str(normalized["entity_id"]), str(normalized["scenario_id"]), int(normalized["locked_budget"]))] = normalized
    scenario_runs = [deduped_rows[key] for key in sorted(deduped_rows)]
    by_entity_budget: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scenario_runs:
        by_entity_budget[(str(row["entity_id"]), int(row["locked_budget"]))].append(row)
        by_entity[str(row["entity_id"])].append(row)
    triple_budget_aggregates = [
        build_entity_budget_aggregate(rows, entity_id=entity_id, locked_budget=locked_budget)
        for (entity_id, locked_budget), rows in sorted(by_entity_budget.items())
    ]
    triple_summary_aggregates = [
        build_entity_summary_aggregate(rows, entity_id=entity_id)
        for entity_id, rows in sorted(by_entity.items())
    ]
    triple_rankings, _unused = _build_rankings(
        triple_summary_aggregates,
        max_structural_failure_rate=float(config["structural_disqualification"]["max_failure_rate"]),
        top_entity_count=1,
    )
    return {
        "schema_version": "odr.model_role_fit.triple_compare.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "continuity_mode": str(config["continuity_mode"]),
        "scenario_set": dict(config["scenario_set"]),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "continuity_mode": str(config["continuity_mode"]),
        },
        "scenario_runs": scenario_runs,
        "triple_budget_aggregates": triple_budget_aggregates,
        "triple_summary_aggregates": triple_summary_aggregates,
        "triple_rankings": triple_rankings,
    }


def build_triple_verdict_payload(
    *,
    triple_compare_payload: dict[str, Any],
    admitted_triples: list[dict[str, Any]],
) -> dict[str, Any]:
    rankings = list(triple_compare_payload.get("triple_rankings") or [])
    best_triple = next(
        (
            row
            for row in rankings
            if not bool(row["structurally_disqualified"]) and not bool(row.get("execution_blocked"))
        ),
        None,
    )
    return {
        "schema_version": "odr.model_role_fit.triple_verdict.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "admitted_triples": admitted_triples,
        "best_observed_triple": str(best_triple["entity_id"]) if best_triple else None,
        "triple_verdicts": rankings,
    }


def build_closeout_payload(
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    pair_compare_payload: dict[str, Any],
    pair_verdict_payload: dict[str, Any],
    triple_compare_payload: dict[str, Any] | None,
    triple_verdict_payload: dict[str, Any] | None,
    skipped_triples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pair_lookup = _pair_id_to_models(registry)
    best_pair_id = pair_verdict_payload.get("best_observed_pair")
    best_pair_spec = pair_lookup.get(str(best_pair_id)) if isinstance(best_pair_id, str) else None
    architect_counts: dict[str, int] = defaultdict(int)
    reviewer_counts: dict[str, int] = defaultdict(int)
    for row in list(pair_verdict_payload.get("pair_verdicts") or []):
        if str(row.get("verdict") or "") in {"structurally_disqualified", "execution_blocked"}:
            continue
        spec = row.get("pair_spec") or {}
        architect = str(spec.get("architect_model") or "").strip()
        reviewer = str(spec.get("reviewer_model") or "").strip()
        if architect:
            architect_counts[architect] += 1
        if reviewer:
            reviewer_counts[reviewer] += 1

    best_architect_model = None
    if best_pair_spec and architect_counts.get(best_pair_spec.architect_model, 0) >= 2:
        best_architect_model = best_pair_spec.architect_model
    best_reviewer_model = None
    if best_pair_spec and reviewer_counts.get(best_pair_spec.reviewer_model, 0) >= 2:
        best_reviewer_model = best_pair_spec.reviewer_model

    triple_phase_status = str(pair_verdict_payload.get("triple_phase_status") or "skipped")
    if triple_verdict_payload is not None and list(triple_verdict_payload.get("admitted_triples") or []):
        triple_phase_status = "completed"
    residual_risk = [
        "Results are bounded to the locked local model inventory, providers, scenarios, budgets, and serial execution order.",
        "The archived continuity conclusion remains background only; this lane does not relitigate continuity as an experimental variable.",
    ]
    admitted_triple_rows = list((triple_verdict_payload or {}).get("admitted_triples") or [])
    return {
        "schema_version": "odr.model_role_fit.closeout.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "best_observed_pair": best_pair_id,
        "best_pair_spec": best_pair_spec.as_dict() if best_pair_spec else None,
        "best_architect_model": best_architect_model,
        "best_reviewer_model": best_reviewer_model,
        "selected_pairs_for_triples": list(pair_verdict_payload.get("selected_pairs_for_triples") or []),
        "best_observed_triple": (
            triple_verdict_payload.get("best_observed_triple") if triple_verdict_payload is not None else None
        ),
        "triple_phase_status": triple_phase_status,
        "triple_phase_skip_reason": pair_verdict_payload.get("triple_phase_skip_reason"),
        "skipped_triples": list(skipped_triples or []),
        "evidence_scope": (
            "serial_pair_matrix_plus_secondary_triples" if admitted_triple_rows else "serial_pair_matrix_only"
        ),
        "residual_risk": residual_risk,
    }
