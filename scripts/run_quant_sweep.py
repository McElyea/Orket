from __future__ import annotations

import argparse
import json
import math
import os
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


REQUIRED_SIDECAR_FIELDS = [
    "vram_total_mb",
    "vram_used_mb",
    "ttft_ms",
    "prefill_tps",
    "decode_tps",
    "thermal_start_c",
    "thermal_end_c",
    "kernel_launch_ms",
    "model_load_ms",
]

OPTIONAL_SIDECAR_FIELDS = [
    "pcie_throughput_gbps",
    "cuda_graph_warmup_ms",
    "gpu_clock_mhz",
    "power_draw_watts",
    "fan_speed_percent",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated quantization sweep and generate vibe summary.")
    parser.add_argument("--model-id", required=True, help="Model id or comma-separated list of model ids.")
    parser.add_argument("--quant-tags", required=True, help="Comma-separated quant tags, e.g. Q8_0,Q6_K,Q4_K_M")
    parser.add_argument("--model-hash", default="")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--runtime-target", "--venue", dest="runtime_target", default="local-hardware")
    parser.add_argument("--execution-mode", "--flow", dest="execution_mode", default="live-card")
    parser.add_argument(
        "--runner-template",
        default=(
            "python scripts/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
    )
    parser.add_argument("--task-limit", type=int, default=0)
    parser.add_argument("--task-id-min", type=int, default=0)
    parser.add_argument("--task-id-max", type=int, default=0)
    parser.add_argument("--out-dir", default="benchmarks/results/quant_sweep")
    parser.add_argument("--summary-out", default="benchmarks/results/quant_sweep/sweep_summary.json")
    parser.add_argument("--matrix-config", default="", help="Optional JSON config file for matrix/session defaults.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved sweep plan and exit.")
    parser.add_argument(
        "--hardware-sidecar-template",
        default="",
        help=(
            "Optional command template executed per quant for hardware diagnostics. "
            "Placeholders: {model_id}, {quant_tag}, {runtime_target}, {execution_mode}, {out_file}."
        ),
    )
    parser.add_argument("--hardware-sidecar-timeout-sec", type=int, default=120, help="Timeout for sidecar command.")
    parser.add_argument("--adherence-threshold", type=float, default=0.95)
    parser.add_argument("--latency-ceiling", type=float, default=10.0, help="Max total latency (seconds) for frontier eligibility.")
    parser.add_argument(
        "--include-invalid",
        "--allow-polluted-frontier",
        dest="include_invalid",
        action="store_true",
        help="Include invalid/polluted quant rows in frontier/recommendation calculations.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Benchmark seed metadata (0 means unset).")
    parser.add_argument("--threads", type=int, default=0, help="Thread-count metadata (0 means unset).")
    parser.add_argument("--affinity-policy", default="", help="CPU affinity policy/mask metadata.")
    parser.add_argument("--warmup-steps", type=int, default=0, help="Warmup steps metadata (0 means unset).")
    parser.add_argument("--canary-runs", type=int, default=0, help="If >0, run canary repeats before matrix execution.")
    parser.add_argument("--canary-task-limit", type=int, default=1, help="Task limit for canary harness run.")
    parser.add_argument(
        "--canary-latency-variance-threshold",
        type=float,
        default=0.03,
        help="Max allowed internal latency coefficient of variation for canary.",
    )
    return parser.parse_args()


def _load_matrix_config(path: str) -> dict[str, Any]:
    config_path = Path(str(path).strip())
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Matrix config must be a JSON object")
    return payload


def _apply_matrix_config(args: argparse.Namespace) -> argparse.Namespace:
    if not str(args.matrix_config or "").strip():
        return args

    config = _load_matrix_config(str(args.matrix_config))
    defaults = {
        "task_bank": "benchmarks/task_bank/v1/tasks.json",
        "runs": 1,
        "runtime_target": "local-hardware",
        "execution_mode": "live-card",
        "runner_template": (
            "python scripts/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
        "task_limit": 0,
        "task_id_min": 0,
        "task_id_max": 0,
        "out_dir": "benchmarks/results/quant_sweep",
        "summary_out": "benchmarks/results/quant_sweep/sweep_summary.json",
        "adherence_threshold": 0.95,
        "latency_ceiling": 10.0,
        "seed": 0,
        "threads": 0,
        "affinity_policy": "",
        "warmup_steps": 0,
        "canary_runs": 0,
        "canary_task_limit": 1,
        "canary_latency_variance_threshold": 0.03,
        "hardware_sidecar_template": "",
        "hardware_sidecar_timeout_sec": 120,
    }
    mapping = {
        "model_id": "models",
        "quant_tags": "quants",
        "task_bank": "task_bank",
        "runs": "runs_per_quant",
        "runtime_target": "runtime_target",
        "execution_mode": "execution_mode",
        "runner_template": "runner_template",
        "task_limit": "task_limit",
        "task_id_min": "task_id_min",
        "task_id_max": "task_id_max",
        "out_dir": "out_dir",
        "summary_out": "summary_out",
        "adherence_threshold": "adherence_threshold",
        "latency_ceiling": "latency_ceiling",
        "seed": "seed",
        "threads": "threads",
        "affinity_policy": "affinity_policy",
        "warmup_steps": "warmup_steps",
        "canary_runs": "canary_runs",
        "canary_task_limit": "canary_task_limit",
        "canary_latency_variance_threshold": "canary_latency_variance_threshold",
        "hardware_sidecar_template": "hardware_sidecar_template",
        "hardware_sidecar_timeout_sec": "hardware_sidecar_timeout_sec",
    }

    for arg_key, cfg_key in mapping.items():
        current = getattr(args, arg_key)
        if arg_key not in {"model_id", "quant_tags"} and current != defaults.get(arg_key):
            continue
        cfg_value = config.get(cfg_key)
        if cfg_value is None:
            continue
        if arg_key == "model_id" and isinstance(cfg_value, list):
            cfg_value = ",".join(str(token).strip() for token in cfg_value if str(token).strip())
        if arg_key == "quant_tags" and isinstance(cfg_value, list):
            cfg_value = ",".join(str(token).strip() for token in cfg_value if str(token).strip())
        setattr(args, arg_key, cfg_value)
    return args


def _run(cmd: list[str], *, env: dict[str, str]) -> None:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        raise SystemExit(result.returncode)


def _git_commit_sha() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _safe_avg(values: list[float]) -> float:
    return round((sum(values) / len(values)), 3) if values else 0.0


def _normalized_token(value: str) -> str:
    token = str(value or "").strip().lower().replace(" ", "_")
    return token or "unknown"


def _hardware_fingerprint() -> str:
    raw_os_family = platform.system().strip().lower()
    if raw_os_family == "darwin":
        raw_os_family = "macos"
    os_family = _normalized_token(raw_os_family)
    os_version = _normalized_token(platform.release())
    cpu_model = _normalized_token(platform.processor() or platform.machine())
    physical_cores = int(psutil.cpu_count(logical=False) or psutil.cpu_count(logical=True) or 0)
    ram_gib = int(round(psutil.virtual_memory().total / float(1024**3)))
    gpu_name = _normalized_token(os.environ.get("ORKET_GPU_NAME", "none"))
    return f"{os_family}-{os_version}|{cpu_model}|{physical_cores}c|{ram_gib}gb|{gpu_name}"


def _quant_rank(tag: str) -> int:
    token = str(tag or "").strip().lower()
    if not token:
        return 0
    if "fp16" in token:
        return 1600
    m = re.search(r"q(\d+)", token)
    if m:
        return int(m.group(1)) * 100
    return 0


def _compute_vibe_delta(*, baseline_adherence: float, baseline_memory_mib: float, adherence: float, memory_mib: float) -> float | None:
    memory_saved_gib = (baseline_memory_mib - memory_mib) / 1024.0
    if memory_saved_gib <= 0:
        return None
    quality_loss = max(0.0, baseline_adherence - adherence)
    return round(quality_loss / memory_saved_gib, 3)


def _is_frontier_eligible(*, row: dict[str, Any], min_adherence: float, latency_ceiling: float) -> bool:
    adherence = float(row.get("adherence_score", 0.0) or 0.0)
    latency = float(row.get("total_latency", 0.0) or 0.0)
    run_quality_status = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
    if run_quality_status != "CLEAN":
        return False
    return adherence >= min_adherence and latency <= latency_ceiling


def _is_frontier_eligible_with_policy(
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
    return _is_frontier_eligible(row=row, min_adherence=min_adherence, latency_ceiling=latency_ceiling)


def _quant_report_out(base_dir: Path, model_id: str, quant_tag: str) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())
    safe_quant = re.sub(r"[^a-zA-Z0-9_.-]+", "_", quant_tag.strip())
    return base_dir / safe_model / f"{safe_quant}_determinism_report.json"


def _sidecar_out(base_dir: Path, model_id: str, quant_tag: str) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())
    safe_quant = re.sub(r"[^a-zA-Z0-9_.-]+", "_", quant_tag.strip())
    return base_dir / "sidecar" / safe_model / f"{safe_quant}_hardware_sidecar.json"


def _default_sidecar_result() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "enabled": False,
        "return_code": None,
        "out_file": "",
        "sidecar_parse_status": "NOT_APPLICABLE",
        "sidecar_parse_errors": [],
    }
    for key in REQUIRED_SIDECAR_FIELDS + OPTIONAL_SIDECAR_FIELDS:
        payload[key] = None
    return payload


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_sidecar_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "vram_total_mb": ["vram_total_mb", "vram_total", "memory_total_mb"],
        "vram_used_mb": ["vram_used_mb", "vram_used", "memory_used_mb"],
        "ttft_ms": ["ttft_ms", "ttft"],
        "prefill_tps": ["prefill_tps", "prompt_tps", "prefill_tokens_per_second"],
        "decode_tps": ["decode_tps", "generation_tps", "decode_tokens_per_second"],
        "thermal_start_c": ["thermal_start_c", "temp_start_c", "temperature_start_c"],
        "thermal_end_c": ["thermal_end_c", "temp_end_c", "temperature_end_c"],
        "kernel_launch_ms": ["kernel_launch_ms", "kernel_ms"],
        "model_load_ms": ["model_load_ms", "load_ms"],
        "pcie_throughput_gbps": ["pcie_throughput_gbps", "pcie_gbps"],
        "cuda_graph_warmup_ms": ["cuda_graph_warmup_ms", "graph_warmup_ms"],
        "gpu_clock_mhz": ["gpu_clock_mhz", "clock_mhz"],
        "power_draw_watts": ["power_draw_watts", "power_watts"],
        "fan_speed_percent": ["fan_speed_percent", "fan_percent"],
    }
    normalized = _default_sidecar_result()
    for canonical, keys in aliases.items():
        value = None
        for key in keys:
            if key in payload:
                value = _coerce_number(payload.get(key))
                break
        normalized[canonical] = value
    return normalized


def _run_sidecar(
    *,
    template: str,
    timeout_sec: int,
    model_id: str,
    quant_tag: str,
    runtime_target: str,
    execution_mode: str,
    out_file: Path,
) -> dict[str, Any]:
    result_payload = _default_sidecar_result()
    if not str(template or "").strip():
        return result_payload

    out_file.parent.mkdir(parents=True, exist_ok=True)
    command = str(template).format(
        model_id=model_id,
        quant_tag=quant_tag,
        runtime_target=runtime_target,
        execution_mode=execution_mode,
        out_file=str(out_file).replace("\\", "/"),
    )
    result = subprocess.run(
        command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        timeout=max(1, int(timeout_sec)),
    )
    stdout = str(result.stdout or "")
    stderr = str(result.stderr or "")
    parsed: dict[str, Any] | None = None
    try:
        payload = json.loads(stdout) if stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        parsed = payload

    normalized = _default_sidecar_result()
    parse_errors: list[str] = []
    parse_status = "OK"
    if int(result.returncode) != 0 and ("nvidia-smi" in stderr.lower() or "nvidia-smi" in stdout.lower()):
        parse_status = "NOT_APPLICABLE"
        parse_errors = ["nvidia_smi_unavailable"]
    elif parsed is None:
        parse_status = "PARSE_ERROR"
        parse_errors = ["invalid_format:sidecar_payload"]
    else:
        normalized = _normalize_sidecar_payload(parsed)
        missing_required = [key for key in REQUIRED_SIDECAR_FIELDS if normalized.get(key) is None]
        missing_optional = [key for key in OPTIONAL_SIDECAR_FIELDS if normalized.get(key) is None]
        if missing_required:
            parse_status = "REQUIRED_FIELD_MISSING"
            parse_errors = [f"missing:{key}" for key in missing_required]
        elif missing_optional:
            parse_status = "OPTIONAL_FIELD_MISSING"
            parse_errors = [f"missing:{key}" for key in missing_optional]
    parse_errors = sorted(parse_errors)

    sidecar_payload = {
        **normalized,
        "enabled": True,
        "command": command,
        "return_code": int(result.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed,
        "sidecar_parse_status": parse_status,
        "sidecar_parse_errors": parse_errors,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    out_file.write_text(json.dumps(sidecar_payload, indent=2) + "\n", encoding="utf-8")
    return {
        **normalized,
        "enabled": True,
        "return_code": int(result.returncode),
        "out_file": str(out_file).replace("\\", "/"),
        "parsed": parsed if isinstance(parsed, dict) else {},
        "sidecar_parse_status": parse_status,
        "sidecar_parse_errors": parse_errors,
    }


def _collect_quant_metrics(report: dict[str, Any]) -> dict[str, Any]:
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
        run_quality_statuses.append(run_quality_status if run_quality_status in {"CLEAN", "POLLUTED"} else "POLLUTED")
        if isinstance(run_quality_reasons, list):
            for reason in run_quality_reasons:
                reason_text = str(reason).strip()
                if reason_text:
                    run_quality_reason_samples.append(reason_text)

    status_priority = {
        "OK": 0,
        "TIMING_UNAVAILABLE": 1,
        "TOKEN_COUNT_UNAVAILABLE": 2,
        "TOKEN_AND_TIMING_UNAVAILABLE": 3,
    }
    aggregate_token_status = "TOKEN_AND_TIMING_UNAVAILABLE"
    if token_statuses:
        aggregate_token_status = sorted(
            token_statuses,
            key=lambda token: status_priority.get(token, 99),
        )[0]
    aggregate_run_quality = "POLLUTED"
    if run_quality_statuses and all(status == "CLEAN" for status in run_quality_statuses):
        aggregate_run_quality = "CLEAN"
    unique_run_quality_reasons = sorted(set(run_quality_reason_samples))
    return {
        "adherence_score": _safe_avg(adherence_samples),
        "peak_memory_rss": _safe_avg(memory_samples),
        "total_latency": _safe_avg(latency_samples),
        "init_latency": _safe_avg(init_latency_samples) if init_latency_samples else None,
        "prompt_tokens_per_second": _safe_avg(prompt_tps_samples) if prompt_tps_samples else None,
        "generation_tokens_per_second": _safe_avg(generation_tps_samples) if generation_tps_samples else None,
        "orchestration_overhead_ratio": _safe_avg(overhead_samples) if overhead_samples else None,
        "token_metrics_status": aggregate_token_status,
        "run_quality_status": aggregate_run_quality,
        "run_quality_reasons": unique_run_quality_reasons,
        "determinism_rate": float(report.get("determinism_rate", 0.0) or 0.0),
        "test_runs": len(test_runs),
    }


def _best_value_quant(
    rows: list[dict[str, Any]],
    *,
    min_adherence: float,
    latency_ceiling: float,
    include_invalid: bool,
) -> dict[str, Any] | None:
    candidates = [
        row
        for row in rows
        if _is_frontier_eligible_with_policy(
            row=row,
            min_adherence=min_adherence,
            latency_ceiling=latency_ceiling,
            include_invalid=include_invalid,
        )
    ]
    if not candidates:
        return None

    def _utility(row: dict[str, Any]) -> float:
        adherence = float(row.get("adherence_score", 0.0) or 0.0)
        latency = float(row.get("total_latency", 0.0) or 0.0)
        if latency <= 0:
            return 0.0
        return adherence / latency

    # Deterministic tie-breakers: highest utility, then adherence, then lower latency, then higher quant rank.
    return sorted(
        candidates,
        key=lambda row: (
            round(_utility(row), 9),
            float(row.get("adherence_score", 0.0) or 0.0),
            -float(row.get("total_latency", 0.0) or 0.0),
            int(row.get("quant_rank", 0) or 0),
        ),
        reverse=True,
    )[0]


def _build_stability_kpis(sessions: list[dict[str, Any]]) -> dict[str, Any]:
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
        if any(
            _is_frontier_eligible(
                row=row,
                min_adherence=min_adherence,
                latency_ceiling=latency_ceiling,
            )
            for row in per_quant
            if isinstance(row, dict)
        ):
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
            run_quality = str(row.get("run_quality_status") or "POLLUTED").strip().upper()
            if run_quality != "CLEAN":
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


def _run_canary(
    *,
    args: argparse.Namespace,
    model_id: str,
    quant_tag: str,
    out_dir: Path,
) -> dict[str, Any]:
    canary_out = out_dir / "_canary_report.json"
    harness_cmd = [
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
        str(canary_out),
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
    env = dict(os.environ)
    env["ORKET_MODEL_ID"] = str(model_id)
    env["ORKET_QUANT_TAG"] = str(quant_tag)
    if str(args.model_hash).strip():
        env["ORKET_MODEL_HASH"] = str(args.model_hash).strip()
    _run(harness_cmd, env=env)

    report = _load_json(canary_out)
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

    adherence_variance = 0.0
    if adherence_values:
        adherence_variance = max(adherence_values) - min(adherence_values)
    latency_variance = None
    if internal_latencies:
        mean_latency = sum(internal_latencies) / len(internal_latencies)
        if mean_latency > 0:
            sq = [(value - mean_latency) ** 2 for value in internal_latencies]
            stdev = math.sqrt(sum(sq) / len(sq))
            latency_variance = stdev / mean_latency
    missing_telemetry_rate = (missing_telemetry_count / len(test_runs)) if test_runs else 1.0

    passed = (
        adherence_variance == 0.0
        and (latency_variance is not None and latency_variance <= float(args.canary_latency_variance_threshold))
        and missing_telemetry_rate == 0.0
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


def main() -> int:
    args = _apply_matrix_config(_parse_args())
    model_ids = [token.strip() for token in str(args.model_id).split(",") if token.strip()]
    if not model_ids:
        raise SystemExit("--model-id must include at least one model id")
    quant_tags = [token.strip() for token in str(args.quant_tags).split(",") if token.strip()]
    if not quant_tags:
        raise SystemExit("--quant-tags must include at least one quant tag")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_out = Path(args.summary_out)
    summary_out.parent.mkdir(parents=True, exist_ok=True)
    commit_sha = _git_commit_sha()

    if args.dry_run:
        dry_plan = {
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
            "out_dir": str(out_dir).replace("\\", "/"),
            "summary_out": str(summary_out).replace("\\", "/"),
            "experimental_controls": {
                "seed": int(args.seed) if int(args.seed) > 0 else None,
                "threads": int(args.threads) if int(args.threads) > 0 else None,
                "affinity_policy": str(args.affinity_policy).strip(),
                "warmup_steps": int(args.warmup_steps) if int(args.warmup_steps) > 0 else None,
            },
            "canary": {
                "enabled": int(args.canary_runs) > 0,
                "runs": int(args.canary_runs),
                "task_limit": int(args.canary_task_limit),
                "latency_variance_threshold": float(args.canary_latency_variance_threshold),
            },
            "hardware_sidecar": {
                "enabled": bool(str(args.hardware_sidecar_template or "").strip()),
                "template": str(args.hardware_sidecar_template),
                "timeout_sec": int(args.hardware_sidecar_timeout_sec),
            },
        }
        print(json.dumps({"dry_run": dry_plan}, indent=2))
        return 0

    canary_result = None
    if int(args.canary_runs) > 0:
        canary_result = _run_canary(
            args=args,
            model_id=model_ids[0],
            quant_tag=quant_tags[0],
            out_dir=out_dir,
        )
        if not bool(canary_result.get("passed")):
            print(json.dumps({"canary": canary_result}, indent=2))
            raise SystemExit("Canary gate failed; aborting quant sweep.")

    sessions: list[dict[str, Any]] = []
    for model_id in model_ids:
        per_quant: list[dict[str, Any]] = []
        for quant_tag in quant_tags:
            raw_out = _quant_report_out(out_dir, model_id, quant_tag)
            raw_out.parent.mkdir(parents=True, exist_ok=True)

            harness_cmd = [
                "python",
                "scripts/run_determinism_harness.py",
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
                str(raw_out),
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
                harness_cmd.extend(["--task-limit", str(args.task_limit)])
            if args.task_id_min > 0:
                harness_cmd.extend(["--task-id-min", str(args.task_id_min)])
            if args.task_id_max > 0:
                harness_cmd.extend(["--task-id-max", str(args.task_id_max)])

            env = dict(os.environ)
            env["ORKET_MODEL_ID"] = str(model_id)
            env["ORKET_QUANT_TAG"] = str(quant_tag)
            if str(args.model_hash).strip():
                env["ORKET_MODEL_HASH"] = str(args.model_hash).strip()

            _run(harness_cmd, env=env)

            report = _load_json(raw_out)
            metrics = _collect_quant_metrics(report)
            sidecar = _run_sidecar(
                template=str(args.hardware_sidecar_template),
                timeout_sec=int(args.hardware_sidecar_timeout_sec),
                model_id=str(model_id),
                quant_tag=str(quant_tag),
                runtime_target=str(args.runtime_target),
                execution_mode=str(args.execution_mode),
                out_file=_sidecar_out(out_dir, str(model_id), str(quant_tag)),
            )
            per_quant.append(
                {
                    "quant_tag": quant_tag,
                    "quant_rank": _quant_rank(quant_tag),
                    "report_path": str(raw_out).replace("\\", "/"),
                    "hardware_sidecar": sidecar,
                    **metrics,
                }
            )

        if not per_quant:
            continue

        baseline = sorted(per_quant, key=lambda row: row["quant_rank"], reverse=True)[0]
        baseline_adherence = float(baseline.get("adherence_score", 0.0) or 0.0)
        baseline_memory = float(baseline.get("peak_memory_rss", 0.0) or 0.0)
        baseline_quant = str(baseline.get("quant_tag") or "")

        for row in per_quant:
            if str(row.get("quant_tag") or "") == baseline_quant:
                row["vibe_delta"] = 0.0
            else:
                row["vibe_delta"] = _compute_vibe_delta(
                    baseline_adherence=baseline_adherence,
                    baseline_memory_mib=baseline_memory,
                    adherence=float(row.get("adherence_score", 0.0) or 0.0),
                    memory_mib=float(row.get("peak_memory_rss", 0.0) or 0.0),
                )
            row["vibe_delta_status"] = "OK"

        target_adherence = baseline_adherence * float(args.adherence_threshold)
        frontier = None
        # Deterministic frontier: scan from the smallest quant rank upward and choose first eligible.
        for row in sorted(per_quant, key=lambda item: item["quant_rank"]):
            if _is_frontier_eligible_with_policy(
                row=row,
                min_adherence=target_adherence,
                latency_ceiling=float(args.latency_ceiling),
                include_invalid=bool(args.include_invalid),
            ):
                frontier = row
                break
        minimum_viable = frontier
        best_value = _best_value_quant(
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
        sessions.append(
            {
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
        )

    if not sessions:
        raise SystemExit("No quant runs collected")

    summary = {
        "schema_version": "1.1.3",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "commit_sha": commit_sha,
        "hardware_fingerprint": _hardware_fingerprint(),
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
            "hardware_sidecar": {
                "enabled": bool(str(args.hardware_sidecar_template or "").strip()),
                "template": str(args.hardware_sidecar_template),
                "timeout_sec": int(args.hardware_sidecar_timeout_sec),
            },
            "runtime_target": str(args.runtime_target),
            "execution_mode": str(args.execution_mode),
            "venue": str(args.runtime_target),
            "flow": str(args.execution_mode),
        },
        "canary": canary_result,
        "sessions": sessions,
    }
    summary["stability_kpis"] = _build_stability_kpis(sessions)

    summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
