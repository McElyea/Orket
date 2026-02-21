from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multi-context sweep and emit linked context ceiling artifact.")
    parser.add_argument("--contexts", required=True, help="Comma-separated contexts, e.g. 4096,8192,16384")
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
    parser.add_argument("--adherence-min", type=float, default=0.0)
    parser.add_argument("--ttft-ceiling-ms", type=float, default=0.0)
    parser.add_argument("--decode-floor-tps", type=float, default=0.0)
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


def main() -> int:
    args = _parse_args()
    contexts = _contexts(args.contexts)
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
        str(float(args.adherence_min)),
        "--ttft-ceiling-ms",
        str(float(args.ttft_ceiling_ms)),
        "--decode-floor-tps",
        str(float(args.decode_floor_tps)),
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
