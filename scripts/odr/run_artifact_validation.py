"""Pure validators for retained ODR shape, leak and trace evidence."""
from __future__ import annotations

from typing import Any


def shape_failures(payload: dict[str, Any], *, architect_model: str, auditor_model: str) -> list[str]:
    failures: list[str] = []
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != 1:
        failures.append("results:expected_single_pair_result")
        return failures
    row = results[0]
    if not isinstance(row, dict):
        failures.append("results:0:not_object")
        return failures
    if str(row.get("architect_model") or "") != architect_model:
        failures.append(f"results:0:architect_model_mismatch:{architect_model}")
    if str(row.get("auditor_model") or "") != auditor_model:
        failures.append(f"results:0:auditor_model_mismatch:{auditor_model}")
    scenarios = row.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        failures.append("results:0:scenarios:missing_or_empty")
        return failures
    for index, scenario in enumerate(scenarios):
        if not isinstance(scenario, dict):
            failures.append(f"results:0:scenarios:{index}:not_object")
            continue
        if not isinstance(scenario.get("final_state"), dict):
            failures.append(f"results:0:scenarios:{index}:final_state_missing")
        if not isinstance(scenario.get("rounds"), list):
            failures.append(f"results:0:scenarios:{index}:rounds_missing")
    return failures


def leak_failures(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for r_index, result in enumerate(payload.get("results", [])):
        if not isinstance(result, dict):
            continue
        for s_index, scenario in enumerate(result.get("scenarios", [])):
            if not isinstance(scenario, dict):
                continue
            for round_row in scenario.get("rounds", []):
                if not isinstance(round_row, dict):
                    continue
                trace = round_row.get("odr_trace_record")
                if not isinstance(trace, dict):
                    continue
                metrics = trace.get("metrics")
                leak_stop = str(trace.get("stop_reason") or "") == "CODE_LEAK"
                leak_metric = isinstance(metrics, dict) and bool(metrics.get("code_leak_hit")) is True
                if leak_stop and leak_metric:
                    failures.append(f"results:{r_index}:scenarios:{s_index}:code_leak_hard")
    return sorted(set(failures))


def trace_failures(payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for r_index, result in enumerate(payload.get("results", [])):
        if not isinstance(result, dict):
            continue
        for s_index, scenario in enumerate(result.get("scenarios", [])):
            if not isinstance(scenario, dict):
                continue
            rounds = scenario.get("rounds")
            if not isinstance(rounds, list):
                failures.append(f"results:{r_index}:scenarios:{s_index}:rounds_not_list")
                continue
            for q_index, round_row in enumerate(rounds):
                if not isinstance(round_row, dict):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:not_object")
                    continue
                trace = round_row.get("odr_trace_record")
                if not isinstance(trace, dict):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_missing")
                    continue
                if not isinstance(trace.get("metrics"), dict):
                    failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_metrics_missing")
                if "stop_reason" not in trace:
                    failures.append(f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:trace_stop_reason_missing")
                metrics = trace.get("metrics") if isinstance(trace.get("metrics"), dict) else {}
                leak_stop = str(trace.get("stop_reason") or "") == "CODE_LEAK"
                leak_metric = bool(metrics.get("code_leak_hit")) is True
                if leak_stop != leak_metric:
                    failures.append(
                        f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:code_leak_propagation_mismatch"
                    )
                if leak_stop:
                    hard = trace.get("code_leak_matches_hard")
                    if not isinstance(hard, list) or not hard:
                        failures.append(
                            f"results:{r_index}:scenarios:{s_index}:rounds:{q_index}:code_leak_matches_hard_missing"
                        )
            final_state = scenario.get("final_state")
            if not isinstance(final_state, dict):
                continue
            history_rounds = final_state.get("history_rounds")
            if not isinstance(history_rounds, list):
                failures.append(f"results:{r_index}:scenarios:{s_index}:final_state_history_rounds_missing")
                continue
            history_round_count = final_state.get("history_round_count")
            if not isinstance(history_round_count, int):
                failures.append(f"results:{r_index}:scenarios:{s_index}:history_round_count_missing")
                continue
            if history_round_count != len(history_rounds):
                failures.append(f"results:{r_index}:scenarios:{s_index}:history_round_count_mismatch")
            if history_round_count != len(rounds):
                failures.append(f"results:{r_index}:scenarios:{s_index}:round_count_mismatch")
    return sorted(set(failures))
