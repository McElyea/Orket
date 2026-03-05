from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

from quant_sweep.config import apply_role_model_env, resolve_canary_task_bounds
from quant_sweep.runtime import load_json, run_cmd


def _build_canary_command(args: argparse.Namespace, out_path: Path) -> list[str]:
    command = [
        "python",
        "scripts/benchmarks/run_determinism_harness.py",
        "--task-bank",
        args.task_bank,
        "--runs",
        str(args.canary_runs),
        "--runtime-target",
        args.runtime_target,
        "--execution-mode",
        args.execution_mode,
        "--runner-template",
        args.runner_template,
        "--output",
        str(out_path),
        "--task-limit",
        str(max(1, int(args.canary_task_limit))),
        "--seed",
        str(args.seed),
        "--threads",
        str(args.threads),
        "--affinity-policy",
        str(args.affinity_policy),
        "--warmup-steps",
        str(args.warmup_steps),
    ]
    task_id_min, task_id_max = resolve_canary_task_bounds(args)
    if task_id_min > 0:
        command.extend(["--task-id-min", str(task_id_min)])
    if task_id_max > 0:
        command.extend(["--task-id-max", str(task_id_max)])
    return command


def _latency_cv(values: list[float]) -> float | None:
    if not values:
        return None
    mean_latency = sum(values) / len(values)
    if mean_latency <= 0:
        return None
    sq = [(value - mean_latency) ** 2 for value in values]
    return math.sqrt(sum(sq) / len(sq)) / mean_latency


def _trim_cold_start(values: list[float], enabled: bool) -> list[float]:
    if not enabled or len(values) <= 1:
        return list(values)
    return list(values[1:])


def _analyze_canary_report(
    report: dict[str, Any],
    *,
    latency_threshold: float,
    drop_first_run: bool,
    max_missing_telemetry_rate: float,
) -> dict[str, Any]:
    test_runs = report.get("test_runs") if isinstance(report.get("test_runs"), list) else []
    adherence_values: list[float] = []
    internal_latencies: list[float] = []
    missing_telemetry_count = 0
    for row in test_runs:
        if not isinstance(row, dict):
            continue
        telemetry = row.get("telemetry") if isinstance(row.get("telemetry"), dict) else {}
        adherence = telemetry.get("adherence_score")
        internal_latency = telemetry.get("internal_model_seconds")
        token_status = str(telemetry.get("token_metrics_status") or "TOKEN_AND_TIMING_UNAVAILABLE").strip()
        if isinstance(adherence, (int, float)):
            adherence_values.append(float(adherence))
        if isinstance(internal_latency, (int, float)):
            internal_latencies.append(float(internal_latency))
        if token_status != "OK":
            missing_telemetry_count += 1

    adherence_variance = (max(adherence_values) - min(adherence_values)) if adherence_values else 0.0
    sampled_internal_latencies = _trim_cold_start(internal_latencies, drop_first_run)
    latency_variance = _latency_cv(sampled_internal_latencies)
    missing_telemetry_rate = (missing_telemetry_count / len(test_runs)) if test_runs else 1.0

    failed_reasons: list[str] = []
    if adherence_variance != 0.0:
        failed_reasons.append("ADHERENCE_VARIANCE_NON_ZERO")
    if latency_variance is None:
        failed_reasons.append("LATENCY_VARIANCE_UNAVAILABLE")
    elif latency_variance > latency_threshold:
        failed_reasons.append("LATENCY_VARIANCE_THRESHOLD_EXCEEDED")
    if missing_telemetry_rate > max_missing_telemetry_rate:
        failed_reasons.append("MISSING_TELEMETRY_RATE_EXCEEDED")

    passed = (
        adherence_variance == 0.0
        and (latency_variance is not None and latency_variance <= latency_threshold)
        and missing_telemetry_rate <= max_missing_telemetry_rate
    )
    return {
        "adherence_variance": adherence_variance,
        "internal_latency_variance": latency_variance,
        "missing_telemetry_rate": missing_telemetry_rate,
        "latency_sample_count_raw": len(internal_latencies),
        "latency_sample_count_used": len(sampled_internal_latencies),
        "drop_first_run": bool(drop_first_run),
        "max_missing_telemetry_rate": float(max_missing_telemetry_rate),
        "failed_reasons": failed_reasons,
        "passed": bool(passed),
    }


def run_canary(
    *,
    args: argparse.Namespace,
    model_id: str,
    quant_tag: str,
    out_dir: Path,
    runtime_env: dict[str, str],
) -> dict[str, Any]:
    canary_out = out_dir / "_canary_report.json"
    task_id_min, task_id_max = resolve_canary_task_bounds(args)
    harness_cmd = _build_canary_command(args, canary_out)
    env = dict(os.environ)
    env.update(runtime_env)
    env["ORKET_MODEL_ID"] = str(model_id)
    env["ORKET_QUANT_TAG"] = str(quant_tag)
    apply_role_model_env(env, str(model_id))
    if str(args.model_hash).strip():
        env["ORKET_MODEL_HASH"] = str(args.model_hash).strip()
    run_cmd(harness_cmd, env=env)

    report = load_json(canary_out)
    analysis = _analyze_canary_report(
        report,
        latency_threshold=float(args.canary_latency_variance_threshold),
        drop_first_run=bool(args.canary_drop_first_run),
        max_missing_telemetry_rate=float(args.canary_max_missing_telemetry_rate),
    )
    return {
        "model_id": str(model_id),
        "quant_tag": str(quant_tag),
        "runs": int(args.canary_runs),
        "task_limit": int(args.canary_task_limit),
        "task_id_min": int(task_id_min),
        "task_id_max": int(task_id_max),
        "adherence_variance": round(float(analysis["adherence_variance"]), 6),
        "internal_latency_variance": (
            round(float(analysis["internal_latency_variance"]), 6)
            if isinstance(analysis["internal_latency_variance"], float)
            else None
        ),
        "missing_telemetry_rate": round(float(analysis["missing_telemetry_rate"]), 6),
        "latency_sample_count_raw": int(analysis["latency_sample_count_raw"]),
        "latency_sample_count_used": int(analysis["latency_sample_count_used"]),
        "drop_first_run": bool(analysis["drop_first_run"]),
        "max_missing_telemetry_rate": float(analysis["max_missing_telemetry_rate"]),
        "latency_variance_threshold": float(args.canary_latency_variance_threshold),
        "failed_reasons": list(analysis["failed_reasons"]),
        "passed": bool(analysis["passed"]),
        "report_path": str(canary_out).replace("\\", "/"),
    }
