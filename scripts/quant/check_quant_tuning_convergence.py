from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
@dataclass
class RunPoint:
    model_id: str
    generated_at: str
    generated_at_epoch: float
    manifest_path: str
    best_task_id: int | None
    score: float | None
    passed: bool
    missing_telemetry_rate: float | None
    latency_variance: float | None
    overhead_ratio: float | None
    polluted_run_rate: float | None
    recommended_overrides: dict[str, Any]
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read quant tuning manifests and report per-model convergence "
            "(STOP/CONTINUE/INSUFFICIENT_DATA)."
        )
    )
    parser.add_argument(
        "--summary-root",
        default="benchmarks/results/quant/quant_sweep/tuning",
        help="Root directory to recursively scan for tuning_manifest.json files.",
    )
    parser.add_argument(
        "--manifest-paths",
        default="",
        help="Optional comma-separated explicit tuning_manifest.json paths.",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Optional comma-separated model filter. Defaults to all models in manifests.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=3,
        help="Number of latest runs per model used for convergence checks.",
    )
    parser.add_argument(
        "--score-epsilon",
        type=float,
        default=0.05,
        help="Maximum score span in the window to treat as plateau.",
    )
    parser.add_argument(
        "--override-epsilon",
        type=float,
        default=0.01,
        help="Maximum allowed numeric override drift in the window.",
    )
    parser.add_argument(
        "--require-all-pass",
        dest="require_all_pass",
        action="store_true",
        default=True,
        help="Require all window runs to have passed probe canary checks (default: enabled).",
    )
    parser.add_argument(
        "--allow-failed-window",
        dest="require_all_pass",
        action="store_false",
        help="Do not require all runs in window to be passed.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output path for JSON report.",
    )
    return parser.parse_args()
def _parse_models(raw: str) -> set[str]:
    models = {token.strip() for token in str(raw or "").split(",") if token.strip()}
    return models
def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
def _parse_timestamp(value: str) -> float:
    raw = str(value or "").strip()
    if not raw:
        return 0.0
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0
def _collect_manifest_paths(summary_root: str, manifest_paths: str) -> list[Path]:
    explicit = [token.strip() for token in str(manifest_paths or "").split(",") if token.strip()]
    if explicit:
        return [Path(token) for token in explicit]
    root = Path(str(summary_root))
    return sorted(root.rglob("tuning_manifest.json"))
def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Manifest must be object: {path}")
    return payload
def _row_to_point(
    *,
    row: dict[str, Any],
    model_id: str,
    generated_at: str,
    manifest_path: Path,
) -> RunPoint:
    probe_results = row.get("probe_results") if isinstance(row.get("probe_results"), list) else []
    top_probe = probe_results[0] if probe_results and isinstance(probe_results[0], dict) else {}
    overrides_raw = row.get("recommended_overrides")
    overrides = overrides_raw if isinstance(overrides_raw, dict) else {}
    best_task_raw = row.get("best_task_id")
    best_task = int(best_task_raw) if isinstance(best_task_raw, int) else None
    return RunPoint(
        model_id=model_id,
        generated_at=generated_at,
        generated_at_epoch=_parse_timestamp(generated_at),
        manifest_path=str(manifest_path).replace("\\", "/"),
        best_task_id=best_task,
        score=_safe_float(top_probe.get("score")),
        passed=bool(top_probe.get("passed")),
        missing_telemetry_rate=_safe_float(top_probe.get("missing_telemetry_rate")),
        latency_variance=_safe_float(top_probe.get("latency_variance")),
        overhead_ratio=_safe_float(top_probe.get("overhead_ratio")),
        polluted_run_rate=_safe_float(top_probe.get("polluted_run_rate")),
        recommended_overrides=overrides,
    )
def _collect_points(
    manifest_paths: list[Path],
    model_filter: set[str],
) -> tuple[dict[str, list[RunPoint]], list[str]]:
    points: dict[str, list[RunPoint]] = {}
    issues: list[str] = []
    for path in manifest_paths:
        if not path.exists():
            issues.append(f"manifest_missing:{path}")
            continue
        try:
            payload = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"manifest_invalid:{path}:{exc}")
            continue
        generated_at = str(payload.get("generated_at") or "")
        rows = payload.get("results") if isinstance(payload.get("results"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("model_id") or "").strip()
            if not model_id:
                continue
            if model_filter and model_id not in model_filter:
                continue
            point = _row_to_point(
                row=row,
                model_id=model_id,
                generated_at=generated_at,
                manifest_path=path,
            )
            points.setdefault(model_id, []).append(point)
    for model_id, rows in points.items():
        rows.sort(key=lambda item: (item.generated_at_epoch, item.generated_at, item.manifest_path))
        points[model_id] = rows
    return points, issues
def _analyze_override_stability(
    window_points: list[RunPoint],
    override_epsilon: float,
) -> tuple[bool, float, list[str]]:
    all_keys: set[str] = set()
    for point in window_points:
        all_keys.update(point.recommended_overrides.keys())
    if not all_keys:
        return False, 0.0, ["recommended_overrides_missing"]
    numeric_max_delta = 0.0
    unstable: list[str] = []
    for key in sorted(all_keys):
        values = [point.recommended_overrides.get(key) for point in window_points]
        if any(value is None for value in values):
            unstable.append(f"override_missing:{key}")
            continue
        numeric_values = [_safe_float(value) for value in values]
        if all(value is not None for value in numeric_values):
            spread = max(numeric_values) - min(numeric_values)
            numeric_max_delta = max(numeric_max_delta, spread)
            if spread > float(override_epsilon):
                unstable.append(f"override_drift:{key}:{round(spread, 6)}")
            continue
        if len({json.dumps(value, sort_keys=True) for value in values}) > 1:
            unstable.append(f"override_changed:{key}")
    return len(unstable) == 0, round(numeric_max_delta, 6), unstable
def _analyze_task_stability(window_points: list[RunPoint]) -> tuple[bool, list[str]]:
    task_ids = [point.best_task_id for point in window_points]
    stable = None not in task_ids and len(set(task_ids)) == 1
    return stable, [] if stable else ["best_task_changed"]
def _analyze_score_window(
    window_points: list[RunPoint],
    score_epsilon: float,
) -> tuple[str, float | None, float | None, list[str]]:
    scores = [point.score for point in window_points if point.score is not None]
    if len(scores) != len(window_points):
        return "UNKNOWN", None, None, ["score_missing"]
    span = round(max(scores) - min(scores), 6)
    delta = round(scores[-1] - scores[0], 6)
    if delta > score_epsilon:
        trend = "IMPROVING"
    elif delta < -score_epsilon:
        trend = "REGRESSING"
    else:
        trend = "PLATEAU"
    reasons = [f"score_span_gt_epsilon:{span}"] if span > score_epsilon else []
    return trend, span, delta, reasons
def _latest_payload(point: RunPoint | None) -> dict[str, Any]:
    if point is None:
        return {}
    return {
        "generated_at": point.generated_at,
        "manifest_path": point.manifest_path,
        "best_task_id": point.best_task_id,
        "score": point.score,
        "passed": point.passed,
        "missing_telemetry_rate": point.missing_telemetry_rate,
        "latency_variance": point.latency_variance,
        "overhead_ratio": point.overhead_ratio,
        "polluted_run_rate": point.polluted_run_rate,
        "recommended_overrides": point.recommended_overrides,
    }
def _analyze_model(
    *,
    model_id: str,
    points: list[RunPoint],
    window: int,
    score_epsilon: float,
    override_epsilon: float,
    require_all_pass: bool,
) -> dict[str, Any]:
    window_points = points[-window:] if len(points) >= window else points[:]
    latest = window_points[-1] if window_points else None
    decision = "CONTINUE" if len(window_points) >= window else "INSUFFICIENT_DATA"
    reasons: list[str] = []
    trend = "UNKNOWN"
    task_stable = False
    score_span: float | None = None
    score_delta: float | None = None
    all_passed = all(point.passed for point in window_points) if window_points else False
    override_stable = False
    override_max_delta: float | None = None
    if len(window_points) < window:
        reasons.append(f"need_{window}_runs_have_{len(window_points)}")
    else:
        task_stable, task_reasons = _analyze_task_stability(window_points)
        reasons.extend(task_reasons)
        trend, score_span, score_delta, score_reasons = _analyze_score_window(
            window_points=window_points,
            score_epsilon=score_epsilon,
        )
        reasons.extend(score_reasons)
        override_stable, override_max_delta_value, override_reasons = _analyze_override_stability(
            window_points=window_points,
            override_epsilon=override_epsilon,
        )
        override_max_delta = override_max_delta_value
        reasons.extend(override_reasons)
        if require_all_pass and not all_passed:
            reasons.append("window_contains_failed_probe")
        if not reasons:
            decision = "STOP"
    return {
        "model_id": model_id,
        "decision": decision,
        "trend": trend,
        "reasons": reasons,
        "total_runs_seen": len(points),
        "window_runs": len(window_points),
        "metrics": {
            "task_stable": task_stable,
            "score_span": score_span,
            "score_delta": score_delta,
            "all_passed": all_passed,
            "override_stable": override_stable,
            "override_max_delta": override_max_delta,
            "score_epsilon": float(score_epsilon),
            "override_epsilon": float(override_epsilon),
            "window": int(window),
        },
        "latest": _latest_payload(latest),
    }
def main() -> int:
    args = _parse_args()
    manifest_paths = _collect_manifest_paths(
        summary_root=str(args.summary_root),
        manifest_paths=str(args.manifest_paths or ""),
    )
    model_filter = _parse_models(str(args.models or ""))
    points_by_model, issues = _collect_points(manifest_paths=manifest_paths, model_filter=model_filter)
    model_reports = [
        _analyze_model(
            model_id=model_id,
            points=points,
            window=int(args.window),
            score_epsilon=float(args.score_epsilon),
            override_epsilon=float(args.override_epsilon),
            require_all_pass=bool(args.require_all_pass),
        )
        for model_id, points in sorted(points_by_model.items())
    ]
    if model_filter:
        missing_models = sorted(model_filter - set(points_by_model.keys()))
        for model_id in missing_models:
            model_reports.append(
                {
                    "model_id": model_id,
                    "decision": "INSUFFICIENT_DATA",
                    "trend": "UNKNOWN",
                    "reasons": ["model_not_found_in_manifests"],
                    "total_runs_seen": 0,
                    "window_runs": 0,
                    "metrics": {
                        "task_stable": False,
                        "score_span": None,
                        "score_delta": None,
                        "all_passed": False,
                        "override_stable": False,
                        "override_max_delta": None,
                        "score_epsilon": float(args.score_epsilon),
                        "override_epsilon": float(args.override_epsilon),
                        "window": int(args.window),
                    },
                    "latest": {},
                }
            )
    has_continue = any(report.get("decision") == "CONTINUE" for report in model_reports)
    has_insufficient = any(report.get("decision") == "INSUFFICIENT_DATA" for report in model_reports)
    overall_decision = "STOP" if model_reports and not has_continue and not has_insufficient else "CONTINUE"
    report = {
        "schema_version": "quant_sweep.tuning.convergence.v1",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "summary_root": str(Path(args.summary_root)).replace("\\", "/"),
        "manifest_count": len(manifest_paths),
        "models_requested": sorted(model_filter) if model_filter else [],
        "overall_decision": overall_decision,
        "issues": issues,
        "models": sorted(model_reports, key=lambda row: str(row.get("model_id"))),
    }
    payload = json.dumps(report, indent=2)
    if str(args.out or "").strip():
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
