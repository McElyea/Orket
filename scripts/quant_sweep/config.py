from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from providers.lmstudio_model_cache import clear_loaded_models, default_lmstudio_base_url
from quant_sweep.constants import ROLE_MODEL_ENV_KEYS


def _add_core_args(parser: argparse.ArgumentParser) -> None:
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
            "python scripts/benchmarks/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
    )
    parser.add_argument("--task-limit", type=int, default=0)
    parser.add_argument("--task-id-min", type=int, default=0)
    parser.add_argument("--task-id-max", type=int, default=0)
    parser.add_argument("--out-dir", default="benchmarks/results/benchmarks/quant_sweep")
    parser.add_argument("--summary-out", default="benchmarks/results/quant/quant_sweep/sweep_summary.json")
    parser.add_argument("--matrix-config", default="", help="Optional JSON config file for matrix/session defaults.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved sweep plan and exit.")


def _add_sidecar_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--hardware-sidecar-template",
        default="",
        help=(
            "Optional command template executed per quant for hardware diagnostics. "
            "Placeholders: {model_id}, {quant_tag}, {runtime_target}, {execution_mode}, {out_file}."
        ),
    )
    parser.add_argument("--hardware-sidecar-timeout-sec", type=int, default=120, help="Timeout for sidecar command.")
    parser.add_argument(
        "--hardware-sidecar-profile",
        default="",
        help="Optional sidecar profile name from sidecar profiles config.",
    )
    parser.add_argument(
        "--sidecar-profiles-config",
        default="benchmarks/configs/sidecar_profiles.json",
        help="Path to sidecar profiles config.",
    )


def _add_policy_args(parser: argparse.ArgumentParser) -> None:
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
    parser.add_argument("--execution-lane", default="lab", choices=["ci", "lab"], help="Execution lane label.")
    parser.add_argument(
        "--vram-profile",
        default="safe",
        choices=["safe", "balanced", "stress"],
        help="VRAM safety profile label.",
    )
    _add_canary_args(parser)
    _add_row_quality_policy_args(parser)


def _add_canary_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--canary-runs", type=int, default=0, help="If >0, run canary repeats before matrix execution.")
    parser.add_argument("--canary-task-limit", type=int, default=1, help="Task limit for canary harness run.")
    parser.add_argument(
        "--canary-task-id-min",
        type=int,
        default=0,
        help="Optional inclusive lower-bound task ID for canary filtering (falls back to --task-id-min when unset).",
    )
    parser.add_argument(
        "--canary-task-id-max",
        type=int,
        default=0,
        help="Optional inclusive upper-bound task ID for canary filtering (falls back to --task-id-max when unset).",
    )
    parser.add_argument(
        "--canary-latency-variance-threshold",
        type=float,
        default=0.03,
        help="Max allowed internal latency coefficient of variation for canary.",
    )
    parser.add_argument(
        "--canary-drop-first-run",
        dest="canary_drop_first_run",
        action="store_true",
        default=True,
        help="Drop first canary sample before variance checks to reduce cold-start skew.",
    )
    parser.add_argument(
        "--no-canary-drop-first-run",
        dest="canary_drop_first_run",
        action="store_false",
        help="Disable first-sample drop in canary variance checks.",
    )
    parser.add_argument(
        "--canary-max-missing-telemetry-rate",
        type=float,
        default=0.0,
        help="Maximum allowed fraction of canary runs with missing token/timing telemetry.",
    )


def _add_row_quality_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--row-max-missing-telemetry-rate",
        type=float,
        default=0.0,
        help="Maximum allowed fraction of quant-row runs with missing token/timing telemetry before row is polluted.",
    )
    parser.add_argument(
        "--row-max-orchestration-overhead-ratio",
        type=float,
        default=0.25,
        help="Maximum allowed average orchestration overhead ratio per quant row before row is polluted.",
    )
    parser.add_argument(
        "--row-max-cpu-saturation-rate",
        type=float,
        default=0.0,
        help="Maximum allowed fraction of quant-row runs with HIGH_CPU_SATURATION before row is polluted.",
    )
    parser.add_argument(
        "--row-max-system-load-rate",
        type=float,
        default=0.0,
        help="Maximum allowed fraction of quant-row runs with HIGH_SYSTEM_LOAD before row is polluted.",
    )


def _add_cache_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_true",
        default=True,
        help="Clear loaded LM Studio model instances before and after the sweep when provider is lmstudio.",
    )
    parser.add_argument(
        "--no-sanitize-model-cache",
        dest="sanitize_model_cache",
        action="store_false",
        help="Disable LM Studio model-cache sanitation for this run.",
    )
    parser.add_argument(
        "--lmstudio-base-url",
        default=default_lmstudio_base_url(),
        help="LM Studio base URL used for model-cache sanitation.",
    )
    parser.add_argument(
        "--lmstudio-timeout-sec",
        type=int,
        default=10,
        help="Timeout in seconds for LM Studio model-cache sanitation calls.",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated quantization sweep and generate vibe summary.")
    _add_core_args(parser)
    _add_sidecar_args(parser)
    _add_policy_args(parser)
    _add_cache_args(parser)
    return parser.parse_args()


def _load_json_dict(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def load_matrix_config(path: str) -> dict[str, Any]:
    return _load_json_dict(Path(str(path).strip()))


def load_sidecar_profiles(path: str) -> dict[str, dict[str, Any]]:
    payload = _load_json_dict(Path(str(path).strip()))
    profiles = payload.get("profiles")
    if isinstance(profiles, dict):
        return {str(key): value for key, value in profiles.items() if isinstance(value, dict)}
    return {}


def _matrix_defaults() -> dict[str, Any]:
    return {
        "task_bank": "benchmarks/task_bank/v1/tasks.json",
        "runs": 1,
        "runtime_target": "local-hardware",
        "execution_mode": "live-card",
        "runner_template": (
            "python scripts/benchmarks/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
        "task_limit": 0,
        "task_id_min": 0,
        "task_id_max": 0,
        "out_dir": "benchmarks/results/benchmarks/quant_sweep",
        "summary_out": "benchmarks/results/quant/quant_sweep/sweep_summary.json",
        "adherence_threshold": 0.95,
        "latency_ceiling": 10.0,
        "seed": 0,
        "threads": 0,
        "affinity_policy": "",
        "warmup_steps": 0,
        "execution_lane": "lab",
        "vram_profile": "safe",
        "canary_runs": 0,
        "canary_task_limit": 1,
        "canary_task_id_min": 0,
        "canary_task_id_max": 0,
        "canary_latency_variance_threshold": 0.03,
        "canary_drop_first_run": True,
        "canary_max_missing_telemetry_rate": 0.0,
        "row_max_missing_telemetry_rate": 0.0,
        "row_max_orchestration_overhead_ratio": 0.25,
        "row_max_cpu_saturation_rate": 0.0,
        "row_max_system_load_rate": 0.0,
        "hardware_sidecar_template": "",
        "hardware_sidecar_timeout_sec": 120,
        "hardware_sidecar_profile": "",
        "sidecar_profiles_config": "benchmarks/configs/sidecar_profiles.json",
        "runtime_env": {},
        "sanitize_model_cache": True,
        "lmstudio_base_url": default_lmstudio_base_url(),
        "lmstudio_timeout_sec": 10,
    }


def _matrix_mapping() -> dict[str, str]:
    return {
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
        "execution_lane": "execution_lane",
        "vram_profile": "vram_profile",
        "canary_runs": "canary_runs",
        "canary_task_limit": "canary_task_limit",
        "canary_task_id_min": "canary_task_id_min",
        "canary_task_id_max": "canary_task_id_max",
        "canary_latency_variance_threshold": "canary_latency_variance_threshold",
        "canary_drop_first_run": "canary_drop_first_run",
        "canary_max_missing_telemetry_rate": "canary_max_missing_telemetry_rate",
        "row_max_missing_telemetry_rate": "row_max_missing_telemetry_rate",
        "row_max_orchestration_overhead_ratio": "row_max_orchestration_overhead_ratio",
        "row_max_cpu_saturation_rate": "row_max_cpu_saturation_rate",
        "row_max_system_load_rate": "row_max_system_load_rate",
        "hardware_sidecar_template": "hardware_sidecar_template",
        "hardware_sidecar_timeout_sec": "hardware_sidecar_timeout_sec",
        "hardware_sidecar_profile": "hardware_sidecar_profile",
        "sidecar_profiles_config": "sidecar_profiles_config",
        "runtime_env": "runtime_env",
        "sanitize_model_cache": "sanitize_model_cache",
        "lmstudio_base_url": "lmstudio_base_url",
        "lmstudio_timeout_sec": "lmstudio_timeout_sec",
    }


def _coerce_matrix_value(arg_key: str, cfg_value: Any) -> Any:
    if arg_key in {"model_id", "quant_tags"} and isinstance(cfg_value, list):
        return ",".join(str(token).strip() for token in cfg_value if str(token).strip())
    if arg_key == "runtime_env" and not isinstance(cfg_value, dict):
        raise ValueError("Matrix config key 'runtime_env' must be a JSON object.")
    return cfg_value


def _should_override_arg(arg_key: str, current: Any, defaults: dict[str, Any]) -> bool:
    if arg_key in {"model_id", "quant_tags"}:
        return True
    return current == defaults.get(arg_key)


def apply_matrix_config(args: argparse.Namespace) -> argparse.Namespace:
    if not str(args.matrix_config or "").strip():
        return args
    config = load_matrix_config(str(args.matrix_config))
    if not hasattr(args, "runtime_env"):
        setattr(args, "runtime_env", {})
    defaults = _matrix_defaults()
    mapping = _matrix_mapping()
    for arg_key, cfg_key in mapping.items():
        current = getattr(args, arg_key)
        if not _should_override_arg(arg_key, current, defaults):
            continue
        cfg_value = config.get(cfg_key)
        if cfg_value is None:
            continue
        setattr(args, arg_key, _coerce_matrix_value(arg_key, cfg_value))
    return args


def resolve_runtime_env(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    resolved: dict[str, str] = {}
    for key, value in raw.items():
        env_key = str(key or "").strip()
        if env_key:
            resolved[env_key] = str(value)
    return resolved


def apply_role_model_env(env: dict[str, str], model_id: str) -> None:
    token = str(model_id or "").strip()
    if not token:
        return
    for key in ROLE_MODEL_ENV_KEYS:
        env.setdefault(key, token)
    env.setdefault("ORKET_OPERATOR_MODEL", token)


def resolve_canary_task_bounds(args: argparse.Namespace) -> tuple[int, int]:
    task_id_min = int(getattr(args, "canary_task_id_min", 0) or 0)
    task_id_max = int(getattr(args, "canary_task_id_max", 0) or 0)
    if task_id_min <= 0:
        task_id_min = int(getattr(args, "task_id_min", 0) or 0)
    if task_id_max <= 0:
        task_id_max = int(getattr(args, "task_id_max", 0) or 0)
    return task_id_min, task_id_max


def resolve_sidecar_settings(args: argparse.Namespace) -> tuple[str, int, str]:
    template = str(args.hardware_sidecar_template or "").strip()
    timeout_sec = int(args.hardware_sidecar_timeout_sec)
    profile = str(args.hardware_sidecar_profile or "").strip()
    if template:
        return template, timeout_sec, profile or "custom"
    if not profile:
        return "", timeout_sec, ""
    profiles = load_sidecar_profiles(str(args.sidecar_profiles_config))
    profile_payload = profiles.get(profile)
    if not isinstance(profile_payload, dict):
        raise SystemExit(f"Unknown sidecar profile '{profile}' in {args.sidecar_profiles_config}")
    resolved_template = str(profile_payload.get("template") or "").strip()
    if not resolved_template:
        raise SystemExit(f"Sidecar profile '{profile}' does not define a template")
    resolved_timeout = int(profile_payload.get("timeout_sec", timeout_sec) or timeout_sec)
    return resolved_template, resolved_timeout, profile


def model_cache_sanitation_plan(args: argparse.Namespace, runtime_env: dict[str, str]) -> dict[str, Any]:
    runtime_provider = str(runtime_env.get("ORKET_LLM_PROVIDER") or os.environ.get("ORKET_LLM_PROVIDER") or "").strip().lower()
    requested = bool(args.sanitize_model_cache)
    enabled = requested and runtime_provider == "lmstudio"
    skip_reason = ""
    if not requested:
        skip_reason = "disabled_by_flag"
    elif runtime_provider != "lmstudio":
        skip_reason = "provider_not_lmstudio"
    return {
        "requested": requested,
        "enabled": enabled,
        "runtime_provider": runtime_provider,
        "skip_reason": skip_reason,
        "lmstudio_base_url": str(args.lmstudio_base_url),
        "timeout_sec": int(args.lmstudio_timeout_sec),
    }


def sanitize_model_cache(stage: str, plan: dict[str, Any]) -> dict[str, Any]:
    if not bool(plan.get("enabled")):
        return {"stage": str(stage), "status": "NOT_APPLICABLE", "reason": str(plan.get("skip_reason") or "disabled")}
    return clear_loaded_models(
        stage=str(stage),
        base_url=str(plan.get("lmstudio_base_url") or ""),
        timeout_sec=int(plan.get("timeout_sec") or 10),
        strict=True,
    )
