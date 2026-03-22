from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from scripts.odr.context_continuity_lane import (
    build_pair_budget_aggregate,
    build_primary_budget_aggregate,
    load_lane_config,
    resolve_lane_artifact_path,
)


def _require_thresholds(config: dict[str, Any]) -> dict[str, Any]:
    thresholds = dict(config.get("decision_thresholds") or {})
    v0 = dict(thresholds.get("v0") or {})
    v1 = dict(thresholds.get("v1") or {})
    required = (
        "convergence_gain_min_percentage_points",
        "absolute_converged_case_delta_min",
        "max_active_context_size_ratio_vs_control",
        "max_latency_ratio_vs_control",
    )
    for key in required:
        if key not in v0:
            raise ValueError(f"Lane config decision_thresholds.v0 missing {key}.")
    required_v1 = (
        "convergence_gain_min_percentage_points",
        "absolute_converged_case_delta_min",
        "carry_forward_integrity_gain_min_percentage_points",
        "max_active_context_size_ratio_vs_v0",
        "max_latency_ratio_vs_v0",
    )
    for key in required_v1:
        if key not in v1:
            raise ValueError(f"Lane config decision_thresholds.v1 missing {key}.")
    return thresholds


def _normalize_scenario_run(raw: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pair_id = str(raw.get("pair_id") or "").strip()
    scenario_id = str(raw.get("scenario_id") or "").strip()
    continuity_mode = str(raw.get("continuity_mode") or "").strip()
    locked_budget = int(raw.get("locked_budget") or 0)
    if pair_id not in {pair.pair_id for pair in config["selected_primary_pairs"]}:
        raise ValueError(f"Compare input pair_id is not in the primary lane matrix: {pair_id!r}.")
    if scenario_id not in set(config["scenario_set"]["scenario_ids"]):
        raise ValueError(f"Compare input scenario_id is outside the locked scenario set: {scenario_id!r}.")
    if continuity_mode not in set(config["continuity_modes"]):
        raise ValueError(f"Compare input continuity_mode is not locked in the lane config: {continuity_mode!r}.")
    if locked_budget not in set(config["locked_budgets"]):
        raise ValueError(f"Compare input locked_budget is not a locked lane budget: {locked_budget!r}.")

    latency_samples = [float(value) for value in list(raw.get("round_latency_ms") or [])]
    context_size_byte_samples = [float(value) for value in list(raw.get("round_active_context_size_bytes") or [])]
    context_samples = [float(value) for value in list(raw.get("round_active_context_size_tokens") or [])]
    if not latency_samples:
        raise ValueError(f"Compare input {scenario_id} must declare round_latency_ms.")
    if not context_size_byte_samples:
        raise ValueError(f"Compare input {scenario_id} must declare round_active_context_size_bytes.")

    return {
        "pair_id": pair_id,
        "scenario_id": scenario_id,
        "continuity_mode": continuity_mode,
        "locked_budget": locked_budget,
        "converged": bool(raw.get("converged")),
        "stop_reason": str(raw.get("stop_reason") or "").strip() or None,
        "rounds_consumed": int(raw.get("rounds_consumed") or 0),
        "reopened_decision_count": int(raw.get("reopened_decision_count") or 0),
        "contradiction_count": int(raw.get("contradiction_count") or 0),
        "regression_count": int(raw.get("regression_count") or 0),
        "carry_forward_integrity": float(raw.get("carry_forward_integrity") or 0.0),
        "median_round_latency_ms": float(median(latency_samples)),
        "median_round_active_context_size_bytes": float(median(context_size_byte_samples)),
        "median_round_active_context_size_tokens": float(median(context_samples)) if context_samples else None,
    }


def _pair_budget_aggregates(scenario_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in scenario_runs:
        grouped[(str(row["pair_id"]), int(row["locked_budget"]), str(row["continuity_mode"]))].append(row)

    aggregates: list[dict[str, Any]] = []
    for (pair_id, locked_budget, continuity_mode), rows in sorted(grouped.items()):
        aggregates.append(
            build_pair_budget_aggregate(
                rows,
                pair_id=pair_id,
                locked_budget=locked_budget,
                continuity_mode=continuity_mode,
            )
        )
    return aggregates


def _aggregate_index(pair_budget_aggregates: list[dict[str, Any]]) -> dict[tuple[str, int, str], dict[str, Any]]:
    return {
        (str(row["pair_id"]), int(row["locked_budget"]), str(row["continuity_mode"])): row
        for row in pair_budget_aggregates
    }


def _primary_budget_aggregates(config: dict[str, Any], pair_budget_aggregates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)
    selected_pair_ids = {pair.pair_id for pair in config["selected_primary_pairs"]}
    for row in pair_budget_aggregates:
        if str(row["pair_id"]) not in selected_pair_ids:
            continue
        grouped[(int(row["locked_budget"]), str(row["continuity_mode"]))].append(row)

    aggregates: list[dict[str, Any]] = []
    for (locked_budget, continuity_mode), rows in sorted(grouped.items()):
        aggregates.append(
            build_primary_budget_aggregate(
                rows,
                locked_budget=locked_budget,
                continuity_mode=continuity_mode,
            )
        )
    return aggregates


def _aggregate_index_by_budget(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    return {(int(row["locked_budget"]), str(row["continuity_mode"])): row for row in rows}


def _scenario_run_counts(
    scenario_runs: list[dict[str, Any]],
    *,
    pair_ids: set[str],
    locked_budget: int,
    continuity_mode: str,
) -> tuple[int, int]:
    rows = [
        row
        for row in scenario_runs
        if str(row["pair_id"]) in pair_ids
        and int(row["locked_budget"]) == locked_budget
        and str(row["continuity_mode"]) == continuity_mode
    ]
    return len(rows), sum(1 for row in rows if bool(row["converged"]))


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def _v0_budget_verdicts(
    config: dict[str, Any],
    scenario_runs: list[dict[str, Any]],
    primary_budget_aggregates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    thresholds = _require_thresholds(config)
    v0_thresholds = dict(thresholds["v0"])
    index = _aggregate_index_by_budget(primary_budget_aggregates)
    primary_pair_ids = {pair.pair_id for pair in config["selected_primary_pairs"]}
    verdicts: list[dict[str, Any]] = []

    for locked_budget in list(config["locked_budgets"]):
        control = index[(int(locked_budget), "control_current_replay")]
        v0 = index[(int(locked_budget), "v0_log_derived_replay")]
        _, control_converged_cases = _scenario_run_counts(
            scenario_runs,
            pair_ids=primary_pair_ids,
            locked_budget=int(locked_budget),
            continuity_mode="control_current_replay",
        )
        scenario_run_count, v0_converged_cases = _scenario_run_counts(
            scenario_runs,
            pair_ids=primary_pair_ids,
            locked_budget=int(locked_budget),
            continuity_mode="v0_log_derived_replay",
        )

        convergence_delta_pp = round((float(v0["convergence_rate"]) - float(control["convergence_rate"])) * 100.0, 6)
        absolute_delta = int(v0_converged_cases - control_converged_cases)
        context_ratio = _safe_ratio(
            float(v0["median_round_active_context_size_bytes"]),
            float(control["median_round_active_context_size_bytes"]),
        )
        latency_ratio = _safe_ratio(
            float(v0["median_round_latency_ms"]),
            float(control["median_round_latency_ms"]),
        )

        disqualifying_regressions: list[str] = []
        if convergence_delta_pp < float(v0_thresholds["convergence_gain_min_percentage_points"]):
            disqualifying_regressions.append("convergence_gain_below_threshold")
        if absolute_delta < int(v0_thresholds["absolute_converged_case_delta_min"]):
            disqualifying_regressions.append("absolute_converged_case_delta_below_threshold")
        if float(v0["reopened_decision_rate"]) > float(control["reopened_decision_rate"]):
            disqualifying_regressions.append("reopened_decision_rate_increase")
        if float(v0["contradiction_rate"]) > float(control["contradiction_rate"]):
            disqualifying_regressions.append("contradiction_rate_increase")
        if context_ratio is not None and context_ratio > float(v0_thresholds["max_active_context_size_ratio_vs_control"]):
            disqualifying_regressions.append("active_context_size_ratio_exceeded")
        if latency_ratio is not None and latency_ratio > float(v0_thresholds["max_latency_ratio_vs_control"]):
            disqualifying_regressions.append("latency_ratio_exceeded")

        verdict = (
            "worthwhile_at_5_rounds"
            if not disqualifying_regressions and int(locked_budget) == 5
            else "worthwhile_at_9_rounds"
            if not disqualifying_regressions and int(locked_budget) == 9
            else "not_materially_worthwhile"
        )

        verdicts.append(
            {
                "continuity_mode": "v0_log_derived_replay",
                "locked_budget": int(locked_budget),
                "pair_scope": str(config["pair_scope"]),
                "evidence_scope": str(config["pair_scope"]),
                "verdict": verdict,
                "threshold_inputs": {
                    "scenario_run_count": scenario_run_count,
                    "control": {
                        "convergence_rate": float(control["convergence_rate"]),
                        "reopened_decision_rate": float(control["reopened_decision_rate"]),
                        "contradiction_rate": float(control["contradiction_rate"]),
                        "median_round_latency_ms": float(control["median_round_latency_ms"]),
                        "median_round_active_context_size_bytes": float(
                            control["median_round_active_context_size_bytes"]
                        ),
                        "median_round_active_context_size_tokens": float(
                            control["median_round_active_context_size_tokens"]
                        ) if control.get("median_round_active_context_size_tokens") is not None else None,
                    },
                    "candidate": {
                        "convergence_rate": float(v0["convergence_rate"]),
                        "reopened_decision_rate": float(v0["reopened_decision_rate"]),
                        "contradiction_rate": float(v0["contradiction_rate"]),
                        "median_round_latency_ms": float(v0["median_round_latency_ms"]),
                        "median_round_active_context_size_bytes": float(
                            v0["median_round_active_context_size_bytes"]
                        ),
                        "median_round_active_context_size_tokens": float(
                            v0["median_round_active_context_size_tokens"]
                        ) if v0.get("median_round_active_context_size_tokens") is not None else None,
                    },
                    "thresholds": dict(v0_thresholds),
                    "actual_active_context_size_ratio_vs_control": context_ratio,
                    "actual_latency_ratio_vs_control": latency_ratio,
                },
                "absolute_converged_case_delta": absolute_delta,
                "percentage_point_convergence_delta": convergence_delta_pp,
                "disqualifying_regressions": disqualifying_regressions,
            }
        )
    return verdicts


def _v1_budget_verdicts(
    config: dict[str, Any],
    scenario_runs: list[dict[str, Any]],
    primary_budget_aggregates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    thresholds = _require_thresholds(config)
    v1_thresholds = dict(thresholds["v1"])
    index = _aggregate_index_by_budget(primary_budget_aggregates)
    primary_pair_ids = {pair.pair_id for pair in config["selected_primary_pairs"]}
    verdicts: list[dict[str, Any]] = []

    for locked_budget in list(config["locked_budgets"]):
        v0 = index[(int(locked_budget), "v0_log_derived_replay")]
        v1 = index[(int(locked_budget), "v1_compiled_shared_state")]
        _, v0_converged_cases = _scenario_run_counts(
            scenario_runs,
            pair_ids=primary_pair_ids,
            locked_budget=int(locked_budget),
            continuity_mode="v0_log_derived_replay",
        )
        scenario_run_count, v1_converged_cases = _scenario_run_counts(
            scenario_runs,
            pair_ids=primary_pair_ids,
            locked_budget=int(locked_budget),
            continuity_mode="v1_compiled_shared_state",
        )

        convergence_delta_pp = round((float(v1["convergence_rate"]) - float(v0["convergence_rate"])) * 100.0, 6)
        carry_forward_delta_pp = round(
            (float(v1["carry_forward_integrity"]) - float(v0["carry_forward_integrity"])) * 100.0,
            6,
        )
        absolute_delta = int(v1_converged_cases - v0_converged_cases)
        context_ratio = _safe_ratio(
            float(v1["median_round_active_context_size_bytes"]),
            float(v0["median_round_active_context_size_bytes"]),
        )
        latency_ratio = _safe_ratio(
            float(v1["median_round_latency_ms"]),
            float(v0["median_round_latency_ms"]),
        )

        full_failures: list[str] = []
        if convergence_delta_pp < float(v1_thresholds["convergence_gain_min_percentage_points"]):
            full_failures.append("convergence_gain_below_threshold")
        if absolute_delta < int(v1_thresholds["absolute_converged_case_delta_min"]):
            full_failures.append("absolute_converged_case_delta_below_threshold")
        if float(v1["reopened_decision_rate"]) > float(v0["reopened_decision_rate"]):
            full_failures.append("reopened_decision_rate_increase")
        if float(v1["contradiction_rate"]) > float(v0["contradiction_rate"]):
            full_failures.append("contradiction_rate_increase")
        if context_ratio is not None and context_ratio > float(v1_thresholds["max_active_context_size_ratio_vs_v0"]):
            full_failures.append("active_context_size_ratio_exceeded")
        if latency_ratio is not None and latency_ratio > float(v1_thresholds["max_latency_ratio_vs_v0"]):
            full_failures.append("latency_ratio_exceeded")

        quality_failures: list[str] = []
        if carry_forward_delta_pp < float(v1_thresholds["carry_forward_integrity_gain_min_percentage_points"]):
            quality_failures.append("carry_forward_integrity_gain_below_threshold")
        if convergence_delta_pp < 0.0:
            quality_failures.append("convergence_regressed")
        if absolute_delta < 0:
            quality_failures.append("absolute_converged_case_delta_negative")
        if float(v1["reopened_decision_rate"]) > float(v0["reopened_decision_rate"]):
            quality_failures.append("reopened_decision_rate_increase")
        if float(v1["contradiction_rate"]) > float(v0["contradiction_rate"]):
            quality_failures.append("contradiction_rate_increase")
        if context_ratio is not None and context_ratio > float(v1_thresholds["max_active_context_size_ratio_vs_v0"]):
            quality_failures.append("active_context_size_ratio_exceeded")
        if latency_ratio is not None and latency_ratio > float(v1_thresholds["max_latency_ratio_vs_v0"]):
            quality_failures.append("latency_ratio_exceeded")

        if not full_failures:
            verdict = "worthwhile_at_5_rounds" if int(locked_budget) == 5 else "worthwhile_at_9_rounds"
            disqualifying_regressions = []
        elif not quality_failures:
            verdict = "continuity_quality_success_only"
            disqualifying_regressions = full_failures
        else:
            verdict = "not_materially_worthwhile"
            disqualifying_regressions = quality_failures

        verdicts.append(
            {
                "continuity_mode": "v1_compiled_shared_state",
                "locked_budget": int(locked_budget),
                "pair_scope": str(config["pair_scope"]),
                "evidence_scope": str(config["pair_scope"]),
                "verdict": verdict,
                "threshold_inputs": {
                    "scenario_run_count": scenario_run_count,
                    "baseline": {
                        "convergence_rate": float(v0["convergence_rate"]),
                        "reopened_decision_rate": float(v0["reopened_decision_rate"]),
                        "contradiction_rate": float(v0["contradiction_rate"]),
                        "carry_forward_integrity": float(v0["carry_forward_integrity"]),
                        "median_round_latency_ms": float(v0["median_round_latency_ms"]),
                        "median_round_active_context_size_bytes": float(v0["median_round_active_context_size_bytes"]),
                    },
                    "candidate": {
                        "convergence_rate": float(v1["convergence_rate"]),
                        "reopened_decision_rate": float(v1["reopened_decision_rate"]),
                        "contradiction_rate": float(v1["contradiction_rate"]),
                        "carry_forward_integrity": float(v1["carry_forward_integrity"]),
                        "median_round_latency_ms": float(v1["median_round_latency_ms"]),
                        "median_round_active_context_size_bytes": float(v1["median_round_active_context_size_bytes"]),
                    },
                    "thresholds": dict(v1_thresholds),
                    "actual_active_context_size_ratio_vs_v0": context_ratio,
                    "actual_latency_ratio_vs_v0": latency_ratio,
                    "percentage_point_carry_forward_integrity_delta": carry_forward_delta_pp,
                },
                "absolute_converged_case_delta": absolute_delta,
                "percentage_point_convergence_delta": convergence_delta_pp,
                "disqualifying_regressions": disqualifying_regressions,
            }
        )
    return verdicts


def build_context_continuity_compare_payload_from_rows(
    raw_runs: list[dict[str, Any]],
    *,
    config_path: Path | None = None,
) -> dict[str, Any]:
    config = load_lane_config(config_path)
    if not raw_runs:
        raise ValueError("Compare input must declare scenario_runs.")

    scenario_runs = [_normalize_scenario_run(raw, config) for raw in raw_runs]
    pair_budget_aggregates = _pair_budget_aggregates(scenario_runs)
    primary_budget_aggregates = _primary_budget_aggregates(config, pair_budget_aggregates)
    budget_verdicts = [
        *_v0_budget_verdicts(config, scenario_runs, primary_budget_aggregates),
        *_v1_budget_verdicts(config, scenario_runs, primary_budget_aggregates),
    ]

    return {
        "schema_version": "odr.context_continuity.compare.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "ended_at": datetime.now(UTC).isoformat(),
        "lane_config_snapshot": {
            "config_path": str(config["config_path"]),
            "requirements_authority": str(config["requirements_authority"]),
            "implementation_authority": str(config["implementation_authority"]),
            "decision_thresholds": dict(config.get("decision_thresholds") or {}),
        },
        "evidence_scope": str(config["pair_scope"]),
        "scenario_set": dict(config["scenario_set"]),
        "continuity_modes": list(config["continuity_modes"]),
        "scenario_runs": scenario_runs,
        "pair_budget_aggregates": pair_budget_aggregates,
        "primary_budget_aggregates": primary_budget_aggregates,
        "budget_verdicts": budget_verdicts,
    }


def build_context_continuity_compare_payload(compare_input_path: Path, *, config_path: Path | None = None) -> dict[str, Any]:
    raw_payload = json.loads(compare_input_path.read_text(encoding="utf-8"))
    return build_context_continuity_compare_payload_from_rows(
        list(raw_payload.get("scenario_runs") or []),
        config_path=config_path,
    )


def resolve_default_compare_output_path(config_path: Path | None = None) -> Path:
    config = load_lane_config(config_path)
    return resolve_lane_artifact_path(config, "compare_output")
