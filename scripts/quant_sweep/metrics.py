from __future__ import annotations

import os
import platform
import re
from typing import Any

import psutil

from quant_sweep.constants import VALID_SIDECAR_PARSE_STATUSES


def safe_avg(values: list[float]) -> float:
    return round((sum(values) / len(values)), 3) if values else 0.0


def normalized_token(value: str) -> str:
    token = str(value or "").strip().lower().replace(" ", "_")
    return token or "unknown"


def hardware_fingerprint() -> str:
    raw_os_family = platform.system().strip().lower()
    if raw_os_family == "darwin":
        raw_os_family = "macos"
    os_family = normalized_token(raw_os_family)
    os_version = normalized_token(platform.release())
    cpu_model = normalized_token(platform.processor() or platform.machine())
    physical_cores = int(psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 0)
    ram_gib = int(round(psutil.virtual_memory().total / float(1024**3)))
    gpu_name = normalized_token(os.environ.get("ORKET_GPU_NAME", "none"))
    return f"{os_family}-{os_version}|{cpu_model}|{physical_cores}c|{ram_gib}gb|{gpu_name}"


def quant_rank(tag: str) -> int:
    token = str(tag or "").strip().lower()
    if not token:
        return 0
    if "fp16" in token:
        return 1600
    match = re.search(r"q(\d+)", token)
    if match:
        return int(match.group(1)) * 100
    return 0


def compute_vibe_delta(*, baseline_adherence: float, baseline_memory_mib: float, adherence: float, memory_mib: float) -> float | None:
    memory_saved_gib = (baseline_memory_mib - memory_mib) / 1024.0
    if memory_saved_gib <= 0:
        return None
    quality_loss = max(0.0, baseline_adherence - adherence)
    return round(quality_loss / memory_saved_gib, 3)


def is_row_valid(row: dict[str, Any]) -> bool:
    run_quality_status = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
    if run_quality_status != "CLEAN":
        return False
    token_status = str(row.get("token_metrics_status") or "TOKEN_AND_TIMING_UNAVAILABLE").strip().upper()
    if token_status != "OK":
        return False
    sidecar = row.get("hardware_sidecar")
    if isinstance(sidecar, dict):
        sidecar_status = str(sidecar.get("sidecar_parse_status") or "NOT_APPLICABLE").strip().upper()
        if sidecar_status not in VALID_SIDECAR_PARSE_STATUSES:
            return False
    return True


def is_frontier_eligible(*, row: dict[str, Any], min_adherence: float, latency_ceiling: float) -> bool:
    if not is_row_valid(row):
        return False
    adherence = float(row.get("adherence_score", 0.0) or 0.0)
    latency = float(row.get("total_latency", 0.0) or 0.0)
    return adherence >= min_adherence and latency <= latency_ceiling


def is_frontier_eligible_with_policy(
    *,
    row: dict[str, Any],
    min_adherence: float,
    latency_ceiling: float,
    include_invalid: bool,
) -> bool:
    if include_invalid:
        adherence = float(row.get("adherence_score", 0.0) or 0.0)
        latency = float(row.get("total_latency", 0.0) or 0.0)
        return adherence >= min_adherence and latency <= latency_ceiling
    return is_frontier_eligible(row=row, min_adherence=min_adherence, latency_ceiling=latency_ceiling)


def collect_quant_metrics(report: dict[str, Any]) -> dict[str, Any]:
    test_runs = report.get("test_runs") if isinstance(report.get("test_runs"), list) else []
    adherence_samples: list[float] = []
    memory_samples: list[float] = []
    latency_samples: list[float] = []
    init_latency_samples: list[float] = []
    prompt_tps_samples: list[float] = []
    generation_tps_samples: list[float] = []
    token_statuses: list[str] = []
    run_quality_statuses: list[str] = []
    run_quality_reason_samples: list[str] = []
    overhead_samples: list[float] = []
    for row in test_runs:
        if not isinstance(row, dict):
            continue
        telemetry = row.get("telemetry") if isinstance(row.get("telemetry"), dict) else {}
        adherence = telemetry.get("adherence_score")
        memory = telemetry.get("peak_memory_rss")
        latency = telemetry.get("total_latency")
        init_latency = telemetry.get("init_latency")
        token_metrics = telemetry.get("token_metrics") if isinstance(telemetry.get("token_metrics"), dict) else {}
        throughput = token_metrics.get("throughput") if isinstance(token_metrics.get("throughput"), dict) else {}
        prompt_tps = throughput.get("prompt_tokens_per_second")
        generation_tps = throughput.get("generation_tokens_per_second")
        overhead_ratio = telemetry.get("orchestration_overhead_ratio")
        run_quality_status = str(telemetry.get("run_quality_status") or "POLLUTED").strip().upper()
        run_quality_reasons = telemetry.get("run_quality_reasons")
        token_status = str(
            telemetry.get("token_metrics_status")
            or token_metrics.get("status")
            or "TOKEN_AND_TIMING_UNAVAILABLE"
        ).strip()
        if isinstance(adherence, (int, float)):
            adherence_samples.append(float(adherence))
        if isinstance(memory, (int, float)):
            memory_samples.append(float(memory))
        if isinstance(latency, (int, float)):
            latency_samples.append(float(latency))
        if isinstance(init_latency, (int, float)):
            init_latency_samples.append(float(init_latency))
        if isinstance(prompt_tps, (int, float)):
            prompt_tps_samples.append(float(prompt_tps))
        if isinstance(generation_tps, (int, float)):
            generation_tps_samples.append(float(generation_tps))
        if isinstance(overhead_ratio, (int, float)):
            overhead_samples.append(float(overhead_ratio))
        token_statuses.append(token_status)
        run_quality_statuses.append(run_quality_status)
        if isinstance(run_quality_reasons, list):
            run_quality_reason_samples.extend(str(reason) for reason in run_quality_reasons)
    aggregate_token_status = "TOKEN_AND_TIMING_UNAVAILABLE"
    if token_statuses and all(status == "OK" for status in token_statuses):
        aggregate_token_status = "OK"
    aggregate_run_quality = "POLLUTED"
    if run_quality_statuses and all(status == "CLEAN" for status in run_quality_statuses):
        aggregate_run_quality = "CLEAN"
    unique_run_quality_reasons = sorted(set(run_quality_reason_samples))
    return {
        "adherence_score": safe_avg(adherence_samples),
        "peak_memory_rss": safe_avg(memory_samples),
        "total_latency": safe_avg(latency_samples),
        "init_latency": safe_avg(init_latency_samples) if init_latency_samples else None,
        "prompt_tokens_per_second": safe_avg(prompt_tps_samples) if prompt_tps_samples else None,
        "generation_tokens_per_second": safe_avg(generation_tps_samples) if generation_tps_samples else None,
        "orchestration_overhead_ratio": safe_avg(overhead_samples) if overhead_samples else None,
        "token_metrics_status": aggregate_token_status,
        "run_quality_status": aggregate_run_quality,
        "run_quality_reasons": unique_run_quality_reasons,
        "determinism_rate": float(report.get("determinism_rate", 0.0) or 0.0),
        "test_runs": len(test_runs),
    }


def best_value_quant(
    rows: list[dict[str, Any]],
    *,
    min_adherence: float,
    latency_ceiling: float,
    include_invalid: bool,
) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if is_frontier_eligible_with_policy(
            row=row,
            min_adherence=min_adherence,
            latency_ceiling=latency_ceiling,
            include_invalid=include_invalid,
        )
    ]
    if not candidates:
        return None

    def utility(row: dict[str, Any]) -> float:
        adherence = float(row.get("adherence_score", 0.0) or 0.0)
        latency = float(row.get("total_latency", 0.0) or 0.0)
        if latency <= 0:
            return 0.0
        return adherence / latency

    return sorted(
        candidates,
        key=lambda row: (
            round(utility(row), 9),
            float(row.get("adherence_score", 0.0) or 0.0),
            -float(row.get("total_latency", 0.0) or 0.0),
            int(row.get("quant_rank", 0) or 0),
        ),
        reverse=True,
    )[0]


def build_stability_kpis(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    total_quant_rows = 0
    total_runs = 0
    determinism_weighted = 0.0
    missing_telemetry_runs = 0
    polluted_runs = 0
    frontier_success = 0

    for session in sessions:
        if not isinstance(session, dict):
            continue
        frontier = session.get("efficiency_frontier") if isinstance(session.get("efficiency_frontier"), dict) else {}
        adherence_ratio = float(frontier.get("adherence_threshold", 0.95) or 0.95)
        latency_ceiling = float(frontier.get("latency_ceiling", 0.0) or 0.0)
        per_quant = session.get("per_quant") if isinstance(session.get("per_quant"), list) else []
        baseline_row = None
        if per_quant:
            baseline_row = sorted(
                [row for row in per_quant if isinstance(row, dict)],
                key=lambda row: int(row.get("quant_rank", 0) or 0),
                reverse=True,
            )[0]
        baseline_adherence = float((baseline_row or {}).get("adherence_score", 0.0) or 0.0)
        min_adherence = baseline_adherence * adherence_ratio
        if any(is_frontier_eligible(row=row, min_adherence=min_adherence, latency_ceiling=latency_ceiling) for row in per_quant if isinstance(row, dict)):
            frontier_success += 1
        for row in per_quant:
            if not isinstance(row, dict):
                continue
            total_quant_rows += 1
            run_count = int(row.get("test_runs", 0) or 0)
            run_weight = max(1, run_count)
            total_runs += run_weight
            determinism_weighted += float(row.get("determinism_rate", 0.0) or 0.0) * run_weight
            token_status = str(row.get("token_metrics_status") or "TOKEN_AND_TIMING_UNAVAILABLE").strip()
            if token_status != "OK":
                missing_telemetry_runs += run_weight
            if not is_row_valid(row):
                polluted_runs += run_weight

    sessions_count = len(sessions)
    return {
        "determinism_rate": round((determinism_weighted / total_runs), 6) if total_runs else 0.0,
        "missing_telemetry_rate": round((missing_telemetry_runs / total_runs), 6) if total_runs else 0.0,
        "polluted_run_rate": round((polluted_runs / total_runs), 6) if total_runs else 0.0,
        "frontier_success_rate": round((frontier_success / sessions_count), 6) if sessions_count else 0.0,
        "quant_rows": total_quant_rows,
        "sessions": sessions_count,
        "weighted_runs": total_runs,
    }
