from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CODE_LEAK_PATTERNS = [
    r"(?s)```(?:[^\n]*)\n.*?\n```",
    r"\b(def|class|import|fn|let|const|interface|type)\b",
    r"\b(npm|pip|cargo|docker|venv|node_modules)\b",
]
DEFAULT_CODE_LEAK_RULE_KEYS = {
    DEFAULT_CODE_LEAK_PATTERNS[0]: "fenced_code_block",
    DEFAULT_CODE_LEAK_PATTERNS[1]: "source_keyword",
    DEFAULT_CODE_LEAK_PATTERNS[2]: "tooling_keyword",
}


def _safe_rounds_used(scenario: dict[str, Any]) -> int:
    final_state = scenario.get("final_state")
    if isinstance(final_state, dict):
        value = final_state.get("history_round_count")
        if isinstance(value, int):
            return value
    rounds = scenario.get("rounds")
    if isinstance(rounds, list):
        return len(rounds)
    return 0


def _latest_trace_record(scenario: dict[str, Any]) -> dict[str, Any]:
    final_state = scenario.get("final_state")
    if isinstance(final_state, dict):
        history_rounds = final_state.get("history_rounds")
        if isinstance(history_rounds, list) and history_rounds:
            last = history_rounds[-1]
            if isinstance(last, dict):
                return last
    rounds = scenario.get("rounds")
    if isinstance(rounds, list) and rounds:
        last_round = rounds[-1]
        if isinstance(last_round, dict):
            trace = last_round.get("odr_trace_record")
            if isinstance(trace, dict):
                return trace
    return {}


def _normalized_stop_reason(scenario: dict[str, Any], rounds_used: int) -> str:
    final_state = scenario.get("final_state")
    if isinstance(final_state, dict):
        raw = final_state.get("stop_reason")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    if rounds_used > 0:
        # The live runner stops after configured round budget when ODR has not stopped.
        return "MAX_SCRIPT_ROUNDS"
    return "UNKNOWN"


def _failure_detail(stop_reason: str, scenario: dict[str, Any]) -> str | None:
    trace = _latest_trace_record(scenario)
    metrics = trace.get("metrics") if isinstance(trace.get("metrics"), dict) else {}
    parse_errors = trace.get("parse_errors") if isinstance(trace.get("parse_errors"), list) else []
    run_cfg = trace.get("run_config") if isinstance(trace.get("run_config"), dict) else {}

    if stop_reason == "CODE_LEAK":
        rule_key = _code_leak_rule_key(trace, run_cfg)
        return f"code_leak_rule={rule_key}"
    if stop_reason in {"FORMAT_VIOLATION", "SHAPE_VIOLATION"}:
        if parse_errors:
            first = parse_errors[0]
            if isinstance(first, dict):
                src = first.get("source")
                code = first.get("code")
                return f"{src}:{code}"
        return "parse_error"
    if stop_reason in {"STABLE_DIFF_FLOOR", "DIFF_FLOOR"}:
        diff_ratio = metrics.get("diff_ratio")
        floor = run_cfg.get("diff_floor_pct")
        if isinstance(diff_ratio, (int, float)) and isinstance(floor, (int, float)):
            return f"diff_ratio={diff_ratio:.4f} < floor={floor:.4f}"
        return "stable_rounds_threshold_reached"
    if stop_reason in {"LOOP_DETECTED", "CIRCULARITY"}:
        sim_prev = metrics.get("sim_prev")
        sim_loop = metrics.get("sim_loop")
        if isinstance(sim_prev, (int, float)) and isinstance(sim_loop, (int, float)):
            return f"sim_loop={sim_loop:.4f} sim_prev={sim_prev:.4f}"
        return "loop_similarity_triggered"
    if stop_reason == "MAX_ROUNDS":
        n = metrics.get("n")
        max_rounds = run_cfg.get("max_rounds")
        if isinstance(n, int) and isinstance(max_rounds, int):
            return f"n={n} max_rounds={max_rounds}"
        return "max_rounds_reached"
    if stop_reason == "MAX_SCRIPT_ROUNDS":
        return "odr_not_stopped_within_runner_round_budget"
    return None


def _code_leak_rule_key(trace: dict[str, Any], run_cfg: dict[str, Any]) -> str:
    hard_matches = trace.get("code_leak_matches_hard")
    if isinstance(hard_matches, list) and hard_matches:
        token = str(hard_matches[0] or "")
        if token.startswith("fence_block"):
            return "fenced_code_block"
        if token.startswith("tooling_context:"):
            return "tooling_context"
        if token.startswith("python_struct:") or token.startswith("js_ts_struct:"):
            return "source_structural"
        if token.startswith("fallback_structural_signals"):
            return "pseudo_code_structural"
        return "hard_signal"

    patterns = run_cfg.get("code_leak_patterns")
    configured_patterns = [str(item) for item in patterns] if isinstance(patterns, list) and patterns else list(DEFAULT_CODE_LEAK_PATTERNS)
    normalized = f"{str(trace.get('architect_raw') or '')}\n{str(trace.get('auditor_raw') or '')}"
    for index, pattern in enumerate(configured_patterns):
        if re.search(pattern, normalized) is None:
            continue
        default_key = DEFAULT_CODE_LEAK_RULE_KEYS.get(pattern)
        if default_key:
            return default_key
        return f"custom_pattern_{index}"
    return "unknown"


def _extract_runs_from_file(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, dict):
        return []

    generated_at = payload.get("generated_at")
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    runner_round_budget = config.get("rounds") if isinstance(config.get("rounds"), int) else None

    rows: list[dict[str, Any]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        architect_model = str(result.get("architect_model") or "")
        auditor_model = str(result.get("auditor_model") or "")
        scenarios = result.get("scenarios")
        if not isinstance(scenarios, list):
            scenarios = []

        scenario_rows: list[dict[str, Any]] = []
        for scenario in scenarios:
            if not isinstance(scenario, dict):
                continue
            rounds_used = _safe_rounds_used(scenario)
            stop_reason = _normalized_stop_reason(scenario, rounds_used=rounds_used)
            scenario_rows.append(
                {
                    "scenario_id": scenario.get("scenario_id"),
                    "stop_reason": stop_reason,
                    "rounds_used": rounds_used,
                    "failure_detail": _failure_detail(stop_reason, scenario=scenario),
                }
            )

        run_key = f"{architect_model}__{auditor_model}"
        rows.append(
            {
                "file": path.name,
                "generated_at": generated_at,
                "architect_model": architect_model,
                "auditor_model": auditor_model,
                "run_key": run_key,
                "is_latest_for_key": False,
                "runner_round_budget": runner_round_budget,
                "provenance_ref": f"provenance.json::{path.name}",
                "scenarios": sorted(scenario_rows, key=lambda item: str(item.get("scenario_id") or "")),
            }
        )
    return rows


def generate_index(input_dir: Path, output_path: Path) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        run_rows.extend(_extract_runs_from_file(path))

    run_rows.sort(
        key=lambda item: (
            str(item.get("file") or ""),
            str(item.get("architect_model") or ""),
            str(item.get("auditor_model") or ""),
        )
    )

    latest_by_key: dict[str, tuple[str, int]] = {}
    for idx, row in enumerate(run_rows):
        key = str(row.get("run_key") or "")
        ts = str(row.get("generated_at") or "")
        current = latest_by_key.get(key)
        if current is None or ts >= current[0]:
            latest_by_key[key] = (ts, idx)
    for idx, row in enumerate(run_rows):
        key = str(row.get("run_key") or "")
        row["is_latest_for_key"] = idx == latest_by_key.get(key, ("", -1))[1]

    payload = {
        "index_v": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(input_dir).replace("\\", "/"),
        "provenance_file": "provenance.json",
        "run_count": len(run_rows),
        "runs": run_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ODR live role-matrix summary index.")
    parser.add_argument("--input-dir", default="benchmarks/published/ODR")
    parser.add_argument("--out", default="benchmarks/published/ODR/index.json")
    args = parser.parse_args()

    payload = generate_index(input_dir=Path(args.input_dir), output_path=Path(args.out))
    print(f"Wrote {args.out} (runs={payload['run_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
