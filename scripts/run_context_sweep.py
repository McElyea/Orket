from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-context sweep and emit linked context ceiling artifact.")
    parser.add_argument("--matrix-config", default="", help="Optional matrix config used to resolve sweep defaults.")
    parser.add_argument("--contexts", default="", help="Comma-separated contexts, e.g. 4096,8192,16384")
    parser.add_argument("--context-profile", default="", choices=["", "safe", "balanced", "stress"])
    parser.add_argument("--context-profiles-config", default="benchmarks/configs/context_sweep_profiles.json")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--quant-tags", required=True)
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v2_realworld/tasks.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--runtime-target", default="local-hardware")
    parser.add_argument("--execution-mode", default="live-card")
    parser.add_argument(
        "--runner-template",
        default=(
            "python scripts/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
    )
    parser.add_argument("--task-limit", type=int, default=0)
    parser.add_argument("--execution-lane", default="lab", choices=["ci", "lab"])
    parser.add_argument("--vram-profile", default="safe", choices=["safe", "balanced", "stress"])
    parser.add_argument("--provenance-ref", default="")
    parser.add_argument("--adherence-min", type=float, default=-1.0)
    parser.add_argument("--ttft-ceiling-ms", type=float, default=-1.0)
    parser.add_argument("--decode-floor-tps", type=float, default=-1.0)
    parser.add_argument("--include-invalid", action="store_true")
    parser.add_argument("--out-dir", default="benchmarks/results/context_sweep")
    parser.add_argument("--summary-template", default="context_{context}_summary.json")
    parser.add_argument("--context-ceiling-out", default="context_ceiling.json")
    parser.add_argument("--storage-root", default="")
    parser.add_argument(
        "--storage-mode",
        default="persistent",
        choices=["persistent", "ephemeral"],
        help="persistent writes to orket_storage unless storage-root is set; ephemeral writes under out-dir/.storage.",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--affinity-policy", default="")
    parser.add_argument("--warmup-steps", type=int, default=0)
    return parser.parse_args()


def _run(cmd: list[str], *, env: dict[str, str]) -> None:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise SystemExit(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n{result.stdout}\n{result.stderr}"
        )


def _contexts(raw: str) -> list[int]:
    values = sorted({int(token.strip()) for token in str(raw).split(",") if token.strip()})
    if not values:
        raise SystemExit("No contexts provided")
    return values


def _load_profiles(path: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Context profiles config must be a JSON object")
    profiles = payload.get("profiles")
    if isinstance(profiles, dict):
        return {str(key): value for key, value in profiles.items() if isinstance(value, dict)}
    return {}


def _apply_matrix_config(args: argparse.Namespace) -> argparse.Namespace:
    matrix_path = str(args.matrix_config or "").strip()
    if not matrix_path:
        return args
    payload = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Matrix config must be a JSON object")
    defaults = {
        "contexts": "",
        "context_profile": "",
        "context_profiles_config": "benchmarks/configs/context_sweep_profiles.json",
        "model_id": "",
        "quant_tags": "",
        "task_bank": "benchmarks/task_bank/v2_realworld/tasks.json",
        "runs": 1,
        "runtime_target": "local-hardware",
        "execution_mode": "live-card",
        "runner_template": (
            "python scripts/live_card_benchmark_runner.py --task {task_file} "
            "--runtime-target {runtime_target} --execution-mode {execution_mode} --run-dir {run_dir}"
        ),
        "task_limit": 0,
        "seed": 0,
        "threads": 0,
        "affinity_policy": "",
        "warmup_steps": 0,
        "adherence_min": -1.0,
        "ttft_ceiling_ms": -1.0,
        "decode_floor_tps": -1.0,
    }
    mapping = {
        "contexts": "context_sweep_contexts",
        "context_profile": "context_sweep_profile",
        "context_profiles_config": "context_profiles_config",
        "model_id": "models",
        "quant_tags": "quants",
        "task_bank": "task_bank",
        "runs": "runs_per_quant",
        "runtime_target": "runtime_target",
        "execution_mode": "execution_mode",
        "runner_template": "runner_template",
        "task_limit": "task_limit",
        "seed": "seed",
        "threads": "threads",
        "affinity_policy": "affinity_policy",
        "warmup_steps": "warmup_steps",
        "adherence_min": "context_adherence_min",
        "ttft_ceiling_ms": "context_ttft_ceiling_ms",
        "decode_floor_tps": "context_decode_floor_tps",
    }
    for arg_key, cfg_key in mapping.items():
        current = getattr(args, arg_key)
        if current != defaults.get(arg_key):
            continue
        cfg_value = payload.get(cfg_key)
        if cfg_value is None:
            continue
        if arg_key in {"model_id", "quant_tags"} and isinstance(cfg_value, list):
            cfg_value = ",".join(str(token).strip() for token in cfg_value if str(token).strip())
        if arg_key == "contexts" and isinstance(cfg_value, list):
            cfg_value = ",".join(str(token).strip() for token in cfg_value if str(token).strip())
        setattr(args, arg_key, cfg_value)
    return args


def main() -> int:
    args = _apply_matrix_config(_parse_args())
    contexts_raw = str(args.contexts or "").strip()
    adherence_min = float(args.adherence_min)
    ttft_ceiling_ms = float(args.ttft_ceiling_ms)
    decode_floor_tps = float(args.decode_floor_tps)
    profile = str(args.context_profile or "").strip()
    if profile:
        profiles = _load_profiles(str(args.context_profiles_config))
        profile_payload = profiles.get(profile)
        if not isinstance(profile_payload, dict):
            raise SystemExit(f"Unknown context profile '{profile}' in {args.context_profiles_config}")
        if not contexts_raw:
            profile_contexts = profile_payload.get("contexts")
            if isinstance(profile_contexts, list):
                contexts_raw = ",".join(str(token) for token in profile_contexts)
        if adherence_min < 0:
            adherence_min = float(profile_payload.get("adherence_min", 0.0) or 0.0)
        if ttft_ceiling_ms < 0:
            ttft_ceiling_ms = float(profile_payload.get("ttft_ceiling_ms", 0.0) or 0.0)
        if decode_floor_tps < 0:
            decode_floor_tps = float(profile_payload.get("decode_floor_tps", 0.0) or 0.0)
    if not contexts_raw:
        raise SystemExit("No contexts provided. Set --contexts or --context-profile.")
    if adherence_min < 0:
        adherence_min = 0.0
    if ttft_ceiling_ms < 0:
        ttft_ceiling_ms = 0.0
    if decode_floor_tps < 0:
        decode_floor_tps = 0.0
    contexts = _contexts(contexts_raw)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_storage_root = str(args.storage_root).strip()
    if not resolved_storage_root:
        if str(args.storage_mode) == "ephemeral":
            resolved_storage_root = str((out_dir / ".storage" / "context_ceilings").resolve())
        else:
            resolved_storage_root = "orket_storage/context_ceilings"

    summary_template = str(args.summary_template)
    summary_paths: list[str] = []
    for context in contexts:
        summary_file = out_dir / summary_template.format(context=context)
        summary_paths.append(str(summary_file).replace("\\", "/"))
        cmd = [
            "python",
            "scripts/run_quant_sweep.py",
            "--model-id",
            str(args.model_id),
            "--quant-tags",
            str(args.quant_tags),
            "--task-bank",
            str(args.task_bank),
            "--runs",
            str(int(args.runs)),
            "--runtime-target",
            str(args.runtime_target),
            "--execution-mode",
            str(args.execution_mode),
            "--runner-template",
            str(args.runner_template),
            "--summary-out",
            str(summary_file),
            "--out-dir",
            str(out_dir / f"context_{context}"),
            "--execution-lane",
            str(args.execution_lane),
            "--vram-profile",
            str(args.vram_profile),
            "--seed",
            str(int(args.seed)),
            "--threads",
            str(int(args.threads)),
            "--affinity-policy",
            str(args.affinity_policy),
            "--warmup-steps",
            str(int(args.warmup_steps)),
        ]
        if int(args.task_limit) > 0:
            cmd.extend(["--task-limit", str(int(args.task_limit))])
        if bool(args.include_invalid):
            cmd.append("--include-invalid")
        env = dict(os.environ)
        env["ORKET_CONTEXT_WINDOW"] = str(context)
        _run(cmd, env=env)

    context_out = out_dir / str(args.context_ceiling_out)
    finder_cmd = [
        "python",
        "scripts/context_ceiling_finder.py",
        "--contexts",
        ",".join(str(value) for value in contexts),
        "--summary-template",
        str(out_dir / summary_template).replace("\\", "/"),
        "--model-id",
        str(args.model_id),
        "--adherence-min",
        str(adherence_min),
        "--ttft-ceiling-ms",
        str(ttft_ceiling_ms),
        "--decode-floor-tps",
        str(decode_floor_tps),
        "--execution-lane",
        str(args.execution_lane),
        "--vram-profile",
        str(args.vram_profile),
        "--provenance-ref",
        str(args.provenance_ref),
        "--out",
        str(context_out),
        "--storage-root",
        str(resolved_storage_root),
    ]
    if bool(args.include_invalid):
        finder_cmd.append("--include-invalid")
    _run(finder_cmd, env=dict(os.environ))

    print(
        json.dumps(
            {
                "status": "OK",
                "context_profile": profile,
                "contexts": contexts,
                "summary_paths": summary_paths,
                "context_ceiling_out": str(context_out).replace("\\", "/"),
                "storage_root": str(resolved_storage_root).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
