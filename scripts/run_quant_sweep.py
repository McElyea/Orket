from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run automated quantization sweep and generate vibe summary.")
    parser.add_argument("--model-id", required=True, help="Model id or comma-separated list of model ids.")
    parser.add_argument("--quant-tags", required=True, help="Comma-separated quant tags, e.g. Q8_0,Q6_K,Q4_K_M")
    parser.add_argument("--model-hash", default="")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--venue", default="local-hardware")
    parser.add_argument("--flow", default="live-card")
    parser.add_argument(
        "--runner-template",
        default="python scripts/live_card_benchmark_runner.py --task {task_file} --venue {venue} --flow {flow} --run-dir {run_dir}",
    )
    parser.add_argument("--task-limit", type=int, default=0)
    parser.add_argument("--task-id-min", type=int, default=0)
    parser.add_argument("--task-id-max", type=int, default=0)
    parser.add_argument("--out-dir", default="benchmarks/results/quant_sweep")
    parser.add_argument("--summary-out", default="benchmarks/results/quant_sweep/sweep_summary.json")
    parser.add_argument("--adherence-threshold", type=float, default=0.95)
    return parser.parse_args()


def _run(cmd: list[str], *, env: dict[str, str]) -> None:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip())
        raise SystemExit(result.returncode)


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


def _quant_report_out(base_dir: Path, model_id: str, quant_tag: str) -> Path:
    safe_model = re.sub(r"[^a-zA-Z0-9_.-]+", "_", model_id.strip())
    safe_quant = re.sub(r"[^a-zA-Z0-9_.-]+", "_", quant_tag.strip())
    return base_dir / safe_model / f"{safe_quant}_determinism_report.json"


def _collect_quant_metrics(report: dict[str, Any]) -> dict[str, Any]:
    test_runs = report.get("test_runs") if isinstance(report.get("test_runs"), list) else []
    adherence_samples: list[float] = []
    memory_samples: list[float] = []
    latency_samples: list[float] = []
    init_latency_samples: list[float] = []
    for row in test_runs:
        if not isinstance(row, dict):
            continue
        telemetry = row.get("telemetry") if isinstance(row.get("telemetry"), dict) else {}
        adherence = telemetry.get("adherence_score")
        memory = telemetry.get("peak_memory_rss")
        latency = telemetry.get("total_latency")
        init_latency = telemetry.get("init_latency")
        if isinstance(adherence, (int, float)):
            adherence_samples.append(float(adherence))
        if isinstance(memory, (int, float)):
            memory_samples.append(float(memory))
        if isinstance(latency, (int, float)):
            latency_samples.append(float(latency))
        if isinstance(init_latency, (int, float)):
            init_latency_samples.append(float(init_latency))
    return {
        "adherence_score": _safe_avg(adherence_samples),
        "peak_memory_rss": _safe_avg(memory_samples),
        "total_latency": _safe_avg(latency_samples),
        "init_latency": _safe_avg(init_latency_samples) if init_latency_samples else None,
        "determinism_rate": float(report.get("determinism_rate", 0.0) or 0.0),
        "test_runs": len(test_runs),
    }


def main() -> int:
    args = _parse_args()
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
                "--venue",
                args.venue,
                "--flow",
                args.flow,
                "--runner-template",
                args.runner_template,
                "--output",
                str(raw_out),
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
            per_quant.append(
                {
                    "quant_tag": quant_tag,
                    "quant_rank": _quant_rank(quant_tag),
                    "report_path": str(raw_out).replace("\\", "/"),
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
            row["vibe_delta"] = _compute_vibe_delta(
                baseline_adherence=baseline_adherence,
                baseline_memory_mib=baseline_memory,
                adherence=float(row.get("adherence_score", 0.0) or 0.0),
                memory_mib=float(row.get("peak_memory_rss", 0.0) or 0.0),
            )
            row["vibe_delta_status"] = "OK"

        target_adherence = baseline_adherence * float(args.adherence_threshold)
        frontier_candidates = [
            row for row in per_quant if float(row.get("adherence_score", 0.0) or 0.0) >= target_adherence
        ]
        frontier = None
        if frontier_candidates:
            frontier = sorted(frontier_candidates, key=lambda row: row["quant_rank"])[0]
        optimal = frontier or baseline
        sessions.append(
            {
                "model_id": str(model_id),
                "baseline_quant": baseline_quant,
                "per_quant": sorted(per_quant, key=lambda row: row["quant_rank"], reverse=True),
                "efficiency_frontier": {
                    "adherence_threshold": float(args.adherence_threshold),
                    "optimal_quant_tag": optimal.get("quant_tag"),
                    "reason": (
                        "lowest quant meeting >=95% baseline adherence"
                        if frontier is not None
                        else "no quant met threshold"
                    ),
                },
                "recommendation": f"For this hardware, use {optimal['quant_tag']} for best Vibe.",
            }
        )

    if not sessions:
        raise SystemExit("No quant runs collected")

    summary = {
        "schema_version": "1.1.3",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "hardware_fingerprint": _hardware_fingerprint(),
        "matrix": {
            "models": model_ids,
            "quants": quant_tags,
            "task_bank": str(args.task_bank),
            "runs_per_quant": int(args.runs),
        },
        "sessions": sessions,
    }

    summary_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
