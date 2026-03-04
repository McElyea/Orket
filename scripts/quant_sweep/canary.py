from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
from typing import Any

from quant_sweep.config import apply_role_model_env
from quant_sweep.runtime import load_json, run_cmd


def _build_canary_command(args: argparse.Namespace, out_path: Path) -> list[str]:
    return [
        "python",
        "scripts/run_determinism_harness.py",
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


def _analyze_canary_report(report: dict[str, Any], latency_threshold: float) -> tuple[float, float | None, float, bool]:
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
    latency_variance = None
    if internal_latencies:
        mean_latency = sum(internal_latencies) / len(internal_latencies)
        if mean_latency > 0:
            sq = [(value - mean_latency) ** 2 for value in internal_latencies]
            latency_variance = math.sqrt(sum(sq) / len(sq)) / mean_latency
    missing_telemetry_rate = (missing_telemetry_count / len(test_runs)) if test_runs else 1.0
    passed = (
        adherence_variance == 0.0
        and (latency_variance is not None and latency_variance <= latency_threshold)
        and missing_telemetry_rate == 0.0
    )
    return adherence_variance, latency_variance, missing_telemetry_rate, passed


def run_canary(
    *,
    args: argparse.Namespace,
    model_id: str,
    quant_tag: str,
    out_dir: Path,
    runtime_env: dict[str, str],
) -> dict[str, Any]:
    canary_out = out_dir / "_canary_report.json"
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
    adherence_variance, latency_variance, missing_telemetry_rate, passed = _analyze_canary_report(
        report,
        float(args.canary_latency_variance_threshold),
    )
    return {
        "model_id": str(model_id),
        "quant_tag": str(quant_tag),
        "runs": int(args.canary_runs),
        "task_limit": int(args.canary_task_limit),
        "adherence_variance": round(adherence_variance, 6),
        "internal_latency_variance": round(float(latency_variance), 6) if isinstance(latency_variance, float) else None,
        "missing_telemetry_rate": round(missing_telemetry_rate, 6),
        "latency_variance_threshold": float(args.canary_latency_variance_threshold),
        "passed": bool(passed),
        "report_path": str(canary_out).replace("\\", "/"),
    }
