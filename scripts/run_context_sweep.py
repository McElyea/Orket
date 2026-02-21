from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-context sweep and emit linked context ceiling artifact.")
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
    parser.add_argument("--storage-root", default="orket_storage/context_ceilings")
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


def main() -> int:
    args = _parse_args()
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
        str(args.storage_root),
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
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
