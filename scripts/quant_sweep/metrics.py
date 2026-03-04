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


def _aggregate_run_quality(
    *,
    run_quality_reasons: list[str],
    missing_telemetry_rate: float,
    max_missing_telemetry_rate: float,
    average_overhead_ratio: float | None,
    max_orchestration_overhead_ratio: float,
    cpu_saturation_rate: float,
    max_cpu_saturation_rate: float,
    system_load_rate: float,
    max_system_load_rate: float,
    polluted_count: int,
) -> tuple[str, list[str]]:
    soft_reasons = {
        "MISSING_TOKEN_TIMINGS",
        "HIGH_ORCHESTRATION_OVERHEAD",
        "HIGH_CPU_SATURATION",
        "HIGH_SYSTEM_LOAD",
    }
    observed_reasons = {str(reason).strip().upper() for reason in run_quality_reasons if str(reason).strip()}
    aggregated = [reason for reason in observed_reasons if reason not in soft_reasons]

    if missing_telemetry_rate > max_missing_telemetry_rate:
        aggregated.append("MISSING_TOKEN_TIMINGS")
    if isinstance(average_overhead_ratio, (int, float)):
        if float(average_overhead_ratio) > float(max_orchestration_overhead_ratio):
            aggregated.append("HIGH_ORCHESTRATION_OVERHEAD")
    elif "HIGH_ORCHESTRATION_OVERHEAD" in observed_reasons:
        aggregated.append("HIGH_ORCHESTRATION_OVERHEAD")
    if cpu_saturation_rate > max_cpu_saturation_rate:
        aggregated.append("HIGH_CPU_SATURATION")
    if system_load_rate > max_system_load_rate:
        aggregated.append("HIGH_SYSTEM_LOAD")

    if polluted_count > 0 and not aggregated and not observed_reasons:
        aggregated.append("RUN_QUALITY_STATUS_POLLUTED")

    reasons = sorted(set(aggregated))
    return ("CLEAN" if not reasons else "POLLUTED"), reasons


def _new_metric_samples() -> dict[str, Any]:
    return {
        "adherence_samples": [],
        "memory_samples": [],
        "latency_samples": [],
        "init_latency_samples": [],
        "prompt_tps_samples": [],
        "generation_tps_samples": [],
        "token_statuses": [],
        "run_quality_reason_samples": [],
        "overhead_samples": [],
        "reason_run_counts": {},
        "missing_telemetry_count": 0,
        "polluted_count": 0,
    }


def _append_telemetry_samples(samples: dict[str, Any], telemetry: dict[str, Any]) -> None:
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
        samples["adherence_samples"].append(float(adherence))
    if isinstance(memory, (int, float)):
        samples["memory_samples"].append(float(memory))
    if isinstance(latency, (int, float)):
        samples["latency_samples"].append(float(latency))
    if isinstance(init_latency, (int, float)):
        samples["init_latency_samples"].append(float(init_latency))
    if isinstance(prompt_tps, (int, float)):
        samples["prompt_tps_samples"].append(float(prompt_tps))
    if isinstance(generation_tps, (int, float)):
        samples["generation_tps_samples"].append(float(generation_tps))
    if isinstance(overhead_ratio, (int, float)):
        samples["overhead_samples"].append(float(overhead_ratio))

    samples["token_statuses"].append(token_status)
    if str(token_status).strip().upper() != "OK":
        samples["missing_telemetry_count"] = int(samples["missing_telemetry_count"]) + 1
    if run_quality_status != "CLEAN":
        samples["polluted_count"] = int(samples["polluted_count"]) + 1

    if isinstance(run_quality_reasons, list):
        run_reason_set = {str(reason).strip().upper() for reason in run_quality_reasons if str(reason).strip()}
        samples["run_quality_reason_samples"].extend(run_reason_set)
        reason_run_counts = samples["reason_run_counts"]
        for reason in run_reason_set:
            reason_run_counts[reason] = int(reason_run_counts.get(reason, 0)) + 1


def _sample_quant_runs(test_runs: list[Any]) -> dict[str, Any]:
    samples = _new_metric_samples()
    for row in test_runs:
        if not isinstance(row, dict):
            continue
        telemetry = row.get("telemetry") if isinstance(row.get("telemetry"), dict) else {}
        _append_telemetry_samples(samples, telemetry)
    return samples


def collect_quant_metrics(
    report: dict[str, Any],
    *,
    max_missing_telemetry_rate: float = 0.0,
    max_orchestration_overhead_ratio: float = 0.25,
    max_cpu_saturation_rate: float = 0.0,
    max_system_load_rate: float = 0.0,
) -> dict[str, Any]:
    test_runs = report.get("test_runs") if isinstance(report.get("test_runs"), list) else []
    samples = _sample_quant_runs(test_runs)
    run_count = len(samples["token_statuses"])
    missing_telemetry_count = int(samples["missing_telemetry_count"])
    polluted_count = int(samples["polluted_count"])
    missing_telemetry_rate = (missing_telemetry_count / run_count) if run_count else 1.0
    polluted_run_rate = (polluted_count / run_count) if run_count else 1.0
    cpu_saturation_rate = (samples["reason_run_counts"].get("HIGH_CPU_SATURATION", 0) / run_count) if run_count else 0.0
    system_load_rate = (samples["reason_run_counts"].get("HIGH_SYSTEM_LOAD", 0) / run_count) if run_count else 0.0
    average_overhead_ratio = safe_avg(samples["overhead_samples"]) if samples["overhead_samples"] else None
    aggregate_token_status = "OK" if run_count and missing_telemetry_rate <= max_missing_telemetry_rate else "TOKEN_AND_TIMING_UNAVAILABLE"
    aggregate_run_quality, unique_run_quality_reasons = _aggregate_run_quality(
        run_quality_reasons=samples["run_quality_reason_samples"],
        missing_telemetry_rate=missing_telemetry_rate,
        max_missing_telemetry_rate=float(max_missing_telemetry_rate),
        average_overhead_ratio=average_overhead_ratio,
        max_orchestration_overhead_ratio=float(max_orchestration_overhead_ratio),
        cpu_saturation_rate=float(cpu_saturation_rate),
        max_cpu_saturation_rate=float(max_cpu_saturation_rate),
        system_load_rate=float(system_load_rate),
        max_system_load_rate=float(max_system_load_rate),
        polluted_count=polluted_count,
    )
    return {
        "adherence_score": safe_avg(samples["adherence_samples"]),
        "peak_memory_rss": safe_avg(samples["memory_samples"]),
        "total_latency": safe_avg(samples["latency_samples"]),
        "init_latency": safe_avg(samples["init_latency_samples"]) if samples["init_latency_samples"] else None,
        "prompt_tokens_per_second": safe_avg(samples["prompt_tps_samples"]) if samples["prompt_tps_samples"] else None,
        "generation_tokens_per_second": safe_avg(samples["generation_tps_samples"]) if samples["generation_tps_samples"] else None,
        "orchestration_overhead_ratio": average_overhead_ratio,
        "missing_telemetry_rate": round(float(missing_telemetry_rate), 6),
        "polluted_run_rate": round(float(polluted_run_rate), 6),
        "cpu_saturation_rate": round(float(cpu_saturation_rate), 6),
        "system_load_rate": round(float(system_load_rate), 6),
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
