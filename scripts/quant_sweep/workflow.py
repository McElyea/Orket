from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quant_sweep.config import apply_role_model_env
from quant_sweep.metrics import (
    best_value_quant,
    build_stability_kpis,
    collect_quant_metrics,
    compute_vibe_delta,
    hardware_fingerprint,
    is_frontier_eligible_with_policy,
    is_row_valid,
    quant_rank,
)
from quant_sweep.runtime import load_json, run_cmd
from quant_sweep.sidecar import quant_report_out, run_sidecar, sidecar_out


def resolve_models_and_quants(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    model_ids = [token.strip() for token in str(args.model_id).split(",") if token.strip()]
    if not model_ids:
        raise SystemExit("--model-id must include at least one model id")
    quant_tags = [token.strip() for token in str(args.quant_tags).split(",") if token.strip()]
    if not quant_tags:
        raise SystemExit("--quant-tags must include at least one quant tag")
    return model_ids, quant_tags


def cache_plan_payload(cache_plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "requested": bool(cache_plan.get("requested")),
        "enabled": bool(cache_plan.get("enabled")),
        "runtime_provider": str(cache_plan.get("runtime_provider") or ""),
        "skip_reason": str(cache_plan.get("skip_reason") or ""),
        "lmstudio_base_url": str(cache_plan.get("lmstudio_base_url") or ""),
        "timeout_sec": int(cache_plan.get("timeout_sec") or 10),
    }


def build_dry_plan(
    *,
    args: argparse.Namespace,
    commit_sha: str,
    model_ids: list[str],
    quant_tags: list[str],
    runtime_env: dict[str, str],
    cache_plan: dict[str, Any],
    sidecar_template: str,
    sidecar_timeout_sec: int,
    sidecar_profile: str,
    out_dir: Path,
    summary_out: Path,
) -> dict[str, Any]:
    return {
        "commit_sha": commit_sha,
        "models": model_ids,
        "quants": quant_tags,
        "task_bank": str(args.task_bank),
        "runs_per_quant": int(args.runs),
        "task_limit": int(args.task_limit),
        "task_id_min": int(args.task_id_min),
        "task_id_max": int(args.task_id_max),
        "runtime_target": str(args.runtime_target),
        "execution_mode": str(args.execution_mode),
        "runtime_env": runtime_env,
        "out_dir": str(out_dir).replace("\\", "/"),
        "summary_out": str(summary_out).replace("\\", "/"),
        "experimental_controls": {
            "seed": int(args.seed) if int(args.seed) > 0 else None,
            "threads": int(args.threads) if int(args.threads) > 0 else None,
            "affinity_policy": str(args.affinity_policy).strip(),
            "warmup_steps": int(args.warmup_steps) if int(args.warmup_steps) > 0 else None,
        },
        "execution_lane": str(args.execution_lane),
        "vram_profile": str(args.vram_profile),
        "canary": {
            "enabled": int(args.canary_runs) > 0,
            "runs": int(args.canary_runs),
            "task_limit": int(args.canary_task_limit),
            "latency_variance_threshold": float(args.canary_latency_variance_threshold),
            "drop_first_run": bool(args.canary_drop_first_run),
            "max_missing_telemetry_rate": float(args.canary_max_missing_telemetry_rate),
        },
        "row_quality_policy": {
            "max_missing_telemetry_rate": float(args.row_max_missing_telemetry_rate),
            "max_orchestration_overhead_ratio": float(args.row_max_orchestration_overhead_ratio),
            "max_cpu_saturation_rate": float(args.row_max_cpu_saturation_rate),
            "max_system_load_rate": float(args.row_max_system_load_rate),
        },
        "hardware_sidecar": {
            "enabled": bool(str(sidecar_template).strip()),
            "profile": sidecar_profile,
            "profiles_config": str(args.sidecar_profiles_config),
            "template": str(sidecar_template),
            "timeout_sec": int(sidecar_timeout_sec),
        },
        "model_cache_sanitation": cache_plan_payload(cache_plan),
    }


def run_quant_harness(
    *,
    args: argparse.Namespace,
    model_id: str,
    quant_tag: str,
    runtime_env: dict[str, str],
    out_path: Path,
) -> None:
    cmd = [
        "python",
        "scripts/HighTier/run_determinism_harness.py",
        "--task-bank",
        args.task_bank,
        "--runs",
        str(args.runs),
        "--runtime-target",
        args.runtime_target,
        "--execution-mode",
        args.execution_mode,
        "--runner-template",
        args.runner_template,
        "--output",
        str(out_path),
        "--seed",
        str(args.seed),
        "--threads",
        str(args.threads),
        "--affinity-policy",
        str(args.affinity_policy),
        "--warmup-steps",
        str(args.warmup_steps),
    ]
    if args.task_limit > 0:
        cmd.extend(["--task-limit", str(args.task_limit)])
    if args.task_id_min > 0:
        cmd.extend(["--task-id-min", str(args.task_id_min)])
    if args.task_id_max > 0:
        cmd.extend(["--task-id-max", str(args.task_id_max)])
    env = dict(os.environ)
    env.update(runtime_env)
    env["ORKET_MODEL_ID"] = str(model_id)
    env["ORKET_QUANT_TAG"] = str(quant_tag)
    apply_role_model_env(env, str(model_id))
    if str(args.model_hash).strip():
        env["ORKET_MODEL_HASH"] = str(args.model_hash).strip()
    run_cmd(cmd, env=env)


def build_quant_row(
    *,
    args: argparse.Namespace,
    model_id: str,
    quant_tag: str,
    report_path: Path,
    sidecar_template: str,
    sidecar_timeout_sec: int,
    out_dir: Path,
) -> dict[str, Any]:
    report = load_json(report_path)
    metrics = collect_quant_metrics(
        report,
        max_missing_telemetry_rate=float(args.row_max_missing_telemetry_rate),
        max_orchestration_overhead_ratio=float(args.row_max_orchestration_overhead_ratio),
        max_cpu_saturation_rate=float(args.row_max_cpu_saturation_rate),
        max_system_load_rate=float(args.row_max_system_load_rate),
    )
    sidecar_payload = run_sidecar(
        template=str(sidecar_template),
        timeout_sec=int(sidecar_timeout_sec),
        model_id=str(model_id),
        quant_tag=str(quant_tag),
        runtime_target=str(args.runtime_target),
        execution_mode=str(args.execution_mode),
        out_file=sidecar_out(out_dir, str(model_id), str(quant_tag)),
    )
    row = {
        "quant_tag": quant_tag,
        "quant_rank": quant_rank(quant_tag),
        "report_path": str(report_path).replace("\\", "/"),
        "hardware_sidecar": sidecar_payload,
        **metrics,
        "execution_lane": str(args.execution_lane),
        "vram_profile": str(args.vram_profile),
    }
    row["valid"] = bool(is_row_valid(row))
    return row


def build_session(
    *,
    args: argparse.Namespace,
    model_id: str,
    per_quant: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline = sorted(per_quant, key=lambda row: row["quant_rank"], reverse=True)[0]
    baseline_adherence = float(baseline.get("adherence_score", 0.0) or 0.0)
    baseline_memory = float(baseline.get("peak_memory_rss", 0.0) or 0.0)
    baseline_quant = str(baseline.get("quant_tag") or "")
    for row in per_quant:
        if str(row.get("quant_tag") or "") == baseline_quant:
            row["vibe_delta"] = 0.0
        else:
            row["vibe_delta"] = compute_vibe_delta(
                baseline_adherence=baseline_adherence,
                baseline_memory_mib=baseline_memory,
                adherence=float(row.get("adherence_score", 0.0) or 0.0),
                memory_mib=float(row.get("peak_memory_rss", 0.0) or 0.0),
            )
        row["vibe_delta_status"] = "OK"

    target_adherence = baseline_adherence * float(args.adherence_threshold)
    minimum_viable = None
    for row in sorted(per_quant, key=lambda item: item["quant_rank"]):
        if is_frontier_eligible_with_policy(
            row=row,
            min_adherence=target_adherence,
            latency_ceiling=float(args.latency_ceiling),
            include_invalid=bool(args.include_invalid),
        ):
            minimum_viable = row
            break
    best_value = best_value_quant(
        per_quant,
        min_adherence=target_adherence,
        latency_ceiling=float(args.latency_ceiling),
        include_invalid=bool(args.include_invalid),
    )
    frontier_reason = "lowest quant meeting adherence and latency thresholds"
    recommendation = f"For this hardware, use {minimum_viable['quant_tag']} for best Vibe." if minimum_viable else (
        "No quantization met the vibe threshold; hardware/model mismatch."
    )
    if minimum_viable is None:
        frontier_reason = "no quant met adherence and latency thresholds"
    return {
        "model_id": str(model_id),
        "baseline_quant": baseline_quant,
        "per_quant": sorted(per_quant, key=lambda row: row["quant_rank"], reverse=True),
        "efficiency_frontier": {
            "adherence_threshold": float(args.adherence_threshold),
            "latency_ceiling": float(args.latency_ceiling),
            "minimum_viable_quant_tag": (minimum_viable or {}).get("quant_tag"),
            "best_value_quant_tag": (best_value or {}).get("quant_tag"),
            "optimal_quant_tag": (minimum_viable or {}).get("quant_tag"),
            "reason": frontier_reason,
        },
        "recommendation_detail": {
            "minimum_viable_quant": (minimum_viable or {}).get("quant_tag"),
            "best_value_quant": (best_value or {}).get("quant_tag"),
        },
        "recommendation": recommendation,
    }


def build_summary(
    *,
    args: argparse.Namespace,
    commit_sha: str,
    model_ids: list[str],
    quant_tags: list[str],
    sidecar_template: str,
    sidecar_profile: str,
    sidecar_timeout_sec: int,
    runtime_env: dict[str, str],
    cache_plan: dict[str, Any],
    sanitation_events: list[dict[str, Any]],
    canary_result: dict[str, Any] | None,
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = {
        "schema_version": "1.1.3",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "commit_sha": commit_sha,
        "hardware_fingerprint": hardware_fingerprint(),
        "matrix": {
            "models": model_ids,
            "quants": quant_tags,
            "task_bank": str(args.task_bank),
            "runs_per_quant": int(args.runs),
            "latency_ceiling": float(args.latency_ceiling),
            "experimental_controls": {
                "seed": int(args.seed) if int(args.seed) > 0 else None,
                "threads": int(args.threads) if int(args.threads) > 0 else None,
                "affinity_policy": str(args.affinity_policy).strip(),
                "warmup_steps": int(args.warmup_steps) if int(args.warmup_steps) > 0 else None,
            },
            "execution_lane": str(args.execution_lane),
            "vram_profile": str(args.vram_profile),
            "row_quality_policy": {
                "max_missing_telemetry_rate": float(args.row_max_missing_telemetry_rate),
                "max_orchestration_overhead_ratio": float(args.row_max_orchestration_overhead_ratio),
                "max_cpu_saturation_rate": float(args.row_max_cpu_saturation_rate),
                "max_system_load_rate": float(args.row_max_system_load_rate),
            },
            "hardware_sidecar": {
                "enabled": bool(str(sidecar_template).strip()),
                "profile": sidecar_profile,
                "profiles_config": str(args.sidecar_profiles_config),
                "template": str(sidecar_template),
                "timeout_sec": int(sidecar_timeout_sec),
            },
            "runtime_target": str(args.runtime_target),
            "execution_mode": str(args.execution_mode),
            "venue": str(args.runtime_target),
            "flow": str(args.execution_mode),
            "runtime_env": runtime_env,
            "model_cache_sanitation": {**cache_plan_payload(cache_plan), "events": sanitation_events},
        },
        "execution_lane": str(args.execution_lane),
        "vram_profile": str(args.vram_profile),
        "canary": canary_result,
        "sessions": sessions,
    }
    summary["stability_kpis"] = build_stability_kpis(sessions)
    return summary
