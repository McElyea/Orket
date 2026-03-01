from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from decimal import Decimal, ROUND_HALF_UP
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark tasks repeatedly and report output drift.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--runtime-target", "--venue", dest="runtime_target", default="standard")
    parser.add_argument("--execution-mode", "--flow", dest="execution_mode", default="default")
    parser.add_argument("--output", default="benchmarks/results/determinism_report.json")
    parser.add_argument(
        "--runner-template",
        default="orket run --task {task_file} --runtime-target {runtime_target} --execution-mode {execution_mode}",
        help=(
            "Command template placeholders: {task_file}, {runtime_target}, {execution_mode}, "
            "{venue}, {flow}, {run_dir}, {repo_root}, {workdir}."
        ),
    )
    parser.add_argument(
        "--artifact-glob",
        action="append",
        default=[],
        help="Optional relative glob(s) under run workdir to include in hash input.",
    )
    parser.add_argument(
        "--task-limit",
        type=int,
        default=0,
        help="Optional max number of tasks to run (0 means all).",
    )
    parser.add_argument(
        "--task-id-min",
        type=int,
        default=0,
        help="Optional inclusive lower bound for numeric task ID filtering.",
    )
    parser.add_argument(
        "--task-id-max",
        type=int,
        default=0,
        help="Optional inclusive upper bound for numeric task ID filtering.",
    )
    parser.add_argument("--seed", type=int, default=0, help="Benchmark seed metadata (0 means unset).")
    parser.add_argument("--threads", type=int, default=0, help="Thread-count metadata (0 means unset).")
    parser.add_argument(
        "--affinity-policy",
        default="",
        help="CPU affinity policy/mask metadata (empty means unset).",
    )
    parser.add_argument("--warmup-steps", type=int, default=0, help="Warmup steps metadata (0 means unset).")
    return parser.parse_args()


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Task bank must be a JSON array.")
    return payload


def _normalize_text(raw: str, run_dir: Path, repo_root: Path) -> str:
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(str(run_dir), "<RUN_DIR>")
    text = text.replace(str(repo_root), "<REPO_ROOT>")
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", "<TIMESTAMP>", text)
    text = re.sub(r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.\d+)?", "<TIME>", text)
    return text.strip() + "\n"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _round3(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _extract_last_json_object(raw_output: str) -> dict[str, Any]:
    for line in reversed((raw_output or "").splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {}


def _normalize_telemetry(
    runner_payload: dict[str, Any],
    *,
    elapsed_ms: float,
    exit_code: int,
    execution_lane: str,
    vram_profile: str,
) -> dict[str, Any]:
    telemetry = runner_payload.get("telemetry") if isinstance(runner_payload, dict) else None
    default_token_metrics = {
        "status": "TOKEN_AND_TIMING_UNAVAILABLE",
        "counts": {
            "prompt_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        },
        "latencies": {
            "prefill_seconds": None,
            "decode_seconds": None,
            "total_turn_seconds": _round3(float(elapsed_ms) / 1000.0),
        },
        "throughput": {
            "prompt_tokens_per_second": None,
            "generation_tokens_per_second": None,
        },
        "audit": {
            "raw_usage": {},
            "raw_timings": {},
        },
    }
    default_vibe = {
        "latency_variance": None,
        "code_density": 0.0,
        "gen_retries": 0,
        "vibe_delta": None,
        "vibe_delta_status": "NO_BASELINE",
    }
    default = {
        "execution_lane": execution_lane,
        "vram_profile": vram_profile,
        "init_latency": None,
        "total_latency": _round3(float(elapsed_ms) / 1000.0),
        "peak_memory_rss": 0.0,
        "adherence_score": None if exit_code != 0 else 1.0,
        "internal_model_seconds": None,
        "orchestration_overhead_ratio": None,
        "run_quality_status": "POLLUTED",
        "run_quality_reasons": ["MISSING_EXPERIMENTAL_CONTROLS", "MISSING_TOKEN_TIMINGS"],
        "system_load_start": {},
        "system_load_end": {},
        "experimental_controls": {
            "seed": None,
            "threads": None,
            "affinity_policy": "",
            "warmup_steps": None,
        },
        "token_metrics_status": "TOKEN_AND_TIMING_UNAVAILABLE",
        "token_metrics": default_token_metrics,
        "vibe_metrics": default_vibe,
    }
    if not isinstance(telemetry, dict):
        return default

    telemetry_execution_lane = str(telemetry.get("execution_lane") or execution_lane).strip() or execution_lane
    telemetry_vram_profile = str(telemetry.get("vram_profile") or vram_profile).strip() or vram_profile

    init_latency = telemetry.get("init_latency")
    total_latency = telemetry.get("total_latency")
    peak_memory_rss = telemetry.get("peak_memory_rss")
    adherence_score = telemetry.get("adherence_score")
    token_metrics = telemetry.get("token_metrics") if isinstance(telemetry.get("token_metrics"), dict) else {}
    token_status = str(
        telemetry.get("token_metrics_status")
        or token_metrics.get("status")
        or "TOKEN_AND_TIMING_UNAVAILABLE"
    ).strip()
    if token_status not in {"OK", "TOKEN_COUNT_UNAVAILABLE", "TIMING_UNAVAILABLE", "TOKEN_AND_TIMING_UNAVAILABLE"}:
        token_status = "TOKEN_AND_TIMING_UNAVAILABLE"
    vibe_metrics = telemetry.get("vibe_metrics") if isinstance(telemetry.get("vibe_metrics"), dict) else {}
    vibe_status = str(vibe_metrics.get("vibe_delta_status") or "NO_BASELINE").strip()
    if vibe_status not in {"OK", "NO_BASELINE", "HW_MISMATCH", "REV_MISMATCH"}:
        vibe_status = "NO_BASELINE"
    run_quality_status = str(telemetry.get("run_quality_status") or "POLLUTED").strip().upper()
    if run_quality_status not in {"CLEAN", "POLLUTED"}:
        run_quality_status = "POLLUTED"
    run_quality_reasons_raw = telemetry.get("run_quality_reasons")
    run_quality_reasons = []
    if isinstance(run_quality_reasons_raw, list):
        run_quality_reasons = [str(reason).strip() for reason in run_quality_reasons_raw if str(reason).strip()]
    system_load_start = telemetry.get("system_load_start") if isinstance(telemetry.get("system_load_start"), dict) else {}
    system_load_end = telemetry.get("system_load_end") if isinstance(telemetry.get("system_load_end"), dict) else {}
    controls = telemetry.get("experimental_controls") if isinstance(telemetry.get("experimental_controls"), dict) else {}
    return {
        "execution_lane": telemetry_execution_lane,
        "vram_profile": telemetry_vram_profile,
        "init_latency": _round3(float(init_latency)) if isinstance(init_latency, (int, float)) else None,
        "total_latency": _round3(float(total_latency))
        if isinstance(total_latency, (int, float))
        else default["total_latency"],
        "peak_memory_rss": _round3(float(peak_memory_rss))
        if isinstance(peak_memory_rss, (int, float))
        else default["peak_memory_rss"],
        "adherence_score": _round3(float(adherence_score))
        if isinstance(adherence_score, (int, float))
        else (None if exit_code != 0 else default["adherence_score"]),
        "internal_model_seconds": _round3(float(telemetry.get("internal_model_seconds")))
        if isinstance(telemetry.get("internal_model_seconds"), (int, float))
        else None,
        "orchestration_overhead_ratio": _round3(float(telemetry.get("orchestration_overhead_ratio")))
        if isinstance(telemetry.get("orchestration_overhead_ratio"), (int, float))
        else None,
        "run_quality_status": run_quality_status,
        "run_quality_reasons": run_quality_reasons,
        "system_load_start": system_load_start,
        "system_load_end": system_load_end,
        "experimental_controls": {
            "seed": int(controls.get("seed")) if isinstance(controls.get("seed"), int) else None,
            "threads": int(controls.get("threads")) if isinstance(controls.get("threads"), int) else None,
            "affinity_policy": str(controls.get("affinity_policy", "")).strip(),
            "warmup_steps": int(controls.get("warmup_steps")) if isinstance(controls.get("warmup_steps"), int) else None,
        },
        "token_metrics_status": token_status,
        "token_metrics": {
            "status": token_status,
            "counts": {
                "prompt_tokens": int(token_metrics.get("counts", {}).get("prompt_tokens"))
                if isinstance(token_metrics.get("counts", {}).get("prompt_tokens"), int)
                else None,
                "output_tokens": int(token_metrics.get("counts", {}).get("output_tokens"))
                if isinstance(token_metrics.get("counts", {}).get("output_tokens"), int)
                else None,
                "total_tokens": int(token_metrics.get("counts", {}).get("total_tokens"))
                if isinstance(token_metrics.get("counts", {}).get("total_tokens"), int)
                else None,
            },
            "latencies": {
                "prefill_seconds": _round3(float(token_metrics.get("latencies", {}).get("prefill_seconds")))
                if isinstance(token_metrics.get("latencies", {}).get("prefill_seconds"), (int, float))
                else None,
                "decode_seconds": _round3(float(token_metrics.get("latencies", {}).get("decode_seconds")))
                if isinstance(token_metrics.get("latencies", {}).get("decode_seconds"), (int, float))
                else None,
                "total_turn_seconds": _round3(float(token_metrics.get("latencies", {}).get("total_turn_seconds")))
                if isinstance(token_metrics.get("latencies", {}).get("total_turn_seconds"), (int, float))
                else default_token_metrics["latencies"]["total_turn_seconds"],
            },
            "throughput": {
                "prompt_tokens_per_second": round(
                    float(token_metrics.get("throughput", {}).get("prompt_tokens_per_second")),
                    2,
                )
                if isinstance(token_metrics.get("throughput", {}).get("prompt_tokens_per_second"), (int, float))
                else None,
                "generation_tokens_per_second": round(
                    float(token_metrics.get("throughput", {}).get("generation_tokens_per_second")),
                    2,
                )
                if isinstance(token_metrics.get("throughput", {}).get("generation_tokens_per_second"), (int, float))
                else None,
            },
            "audit": {
                "raw_usage": token_metrics.get("audit", {}).get("raw_usage")
                if isinstance(token_metrics.get("audit", {}).get("raw_usage"), dict)
                else {},
                "raw_timings": token_metrics.get("audit", {}).get("raw_timings")
                if isinstance(token_metrics.get("audit", {}).get("raw_timings"), dict)
                else {},
            },
        },
        "vibe_metrics": {
            "latency_variance": _round3(float(vibe_metrics.get("latency_variance")))
            if isinstance(vibe_metrics.get("latency_variance"), (int, float))
            else None,
            "code_density": _round3(float(vibe_metrics.get("code_density")))
            if isinstance(vibe_metrics.get("code_density"), (int, float))
            else 0.0,
            "gen_retries": int(vibe_metrics.get("gen_retries") or 0),
            "vibe_delta": _round3(float(vibe_metrics.get("vibe_delta")))
            if isinstance(vibe_metrics.get("vibe_delta"), (int, float))
            else None,
            "vibe_delta_status": vibe_status,
        },
    }


def _run_once(
    task: dict[str, Any],
    run_index: int,
    runtime_target: str,
    execution_mode: str,
    runner_template: str,
    artifact_globs: list[str],
    *,
    seed: int,
    threads: int,
    affinity_policy: str,
    warmup_steps: int,
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="orket_det_") as temp_dir:
        run_dir = Path(temp_dir)
        task_file = run_dir / "task.json"
        task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")

        command = runner_template.format(
            task_file=str(task_file),
            runtime_target=runtime_target,
            execution_mode=execution_mode,
            venue=runtime_target,
            flow=execution_mode,
            seed=str(seed),
            threads=str(threads),
            affinity_policy=str(affinity_policy),
            warmup_steps=str(warmup_steps),
            workdir=str(run_dir),
            run_dir=str(run_dir),
            repo_root=str(repo_root),
        )

        env = os.environ.copy()
        env["ORKET_BENCH_SEED"] = str(seed)
        env["ORKET_BENCH_THREADS"] = str(threads)
        env["ORKET_BENCH_AFFINITY_POLICY"] = str(affinity_policy)
        env["ORKET_BENCH_WARMUP_STEPS"] = str(warmup_steps)
        started = time.perf_counter()
        argv = shlex.split(command, posix=os.name != "nt")
        if not argv:
            raise ValueError("runner-template resolved to an empty command")
        result = subprocess.run(
            argv,
            shell=False,
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw_output = (result.stdout or "") + "\n" + (result.stderr or "")
        runner_payload = _extract_last_json_object(raw_output)
        telemetry = _normalize_telemetry(
            runner_payload=runner_payload,
            elapsed_ms=elapsed_ms,
            exit_code=int(result.returncode),
            execution_lane=("lab" if str(runtime_target).strip().lower() in {"lab", "gpu", "selfhosted"} else "ci"),
            vram_profile=(str(os.environ.get("ORKET_VRAM_PROFILE", "")).strip() or "safe"),
        )
        outcome = "pass" if int(result.returncode) == 0 else "fail"

        artifact_payload = []
        for glob_pattern in artifact_globs:
            for path in sorted(run_dir.glob(glob_pattern)):
                if path.is_file():
                    artifact_payload.append(
                        {
                            "path": str(path.relative_to(run_dir)).replace("\\", "/"),
                            "content": path.read_text(encoding="utf-8", errors="replace"),
                        }
                    )

        combined_payload = {
            "exit_code": int(result.returncode),
            "stdout_stderr": raw_output,
            "artifacts": artifact_payload,
        }
        normalized = _normalize_text(
            json.dumps(combined_payload, sort_keys=True),
            run_dir=run_dir,
            repo_root=repo_root,
        )
        digest = _sha256(normalized)
        return {
            "run_index": run_index,
            "exit_code": int(result.returncode),
            "outcome": outcome,
            "hash": digest,
            "duration_ms": elapsed_ms,
            "cost_usd": 0.0,
            "telemetry": telemetry,
            "normalized_output_preview": normalized[:300],
        }


def main() -> int:
    args = _parse_args()
    task_bank_path = Path(args.task_bank)
    tasks = _load_tasks(task_bank_path)
    if args.task_id_min > 0:
        tasks = [task for task in tasks if int(task.get("id", 0)) >= int(args.task_id_min)]
    if args.task_id_max > 0:
        tasks = [task for task in tasks if int(task.get("id", 0)) <= int(args.task_id_max)]
    if args.task_limit > 0:
        tasks = tasks[: args.task_limit]

    details: dict[str, Any] = {}
    deterministic_count = 0
    latency_samples: list[float] = []
    cost_samples: list[float] = []
    test_runs: list[dict[str, Any]] = []
    for task in tasks:
        task_id = str(task.get("id", "unknown"))
        runs = [
            _run_once(
                task=task,
                run_index=index + 1,
                runtime_target=str(args.runtime_target),
                execution_mode=str(args.execution_mode),
                runner_template=str(args.runner_template),
                artifact_globs=list(args.artifact_glob),
                seed=int(args.seed),
                threads=int(args.threads),
                affinity_policy=str(args.affinity_policy),
                warmup_steps=int(args.warmup_steps),
            )
            for index in range(int(args.runs))
        ]
        hashes = [entry["hash"] for entry in runs]
        run_latencies = [float(entry.get("duration_ms", 0.0) or 0.0) for entry in runs]
        run_costs = [float(entry.get("cost_usd", 0.0) or 0.0) for entry in runs]
        latency_samples.extend(run_latencies)
        cost_samples.extend(run_costs)
        unique_hashes = sorted(set(hashes))
        is_deterministic = len(unique_hashes) == 1
        if is_deterministic:
            deterministic_count += 1

        details[task_id] = {
            "tier": task.get("tier"),
            "unique_hashes": len(unique_hashes),
            "deterministic": is_deterministic,
            "avg_latency_ms": round(sum(run_latencies) / len(run_latencies), 3) if run_latencies else 0.0,
            "avg_cost_usd": round(sum(run_costs) / len(run_costs), 6) if run_costs else 0.0,
            "hashes": hashes,
            "runs": runs,
        }
        for run in runs:
            if not isinstance(run, dict):
                continue
            test_runs.append(
                {
                    "test_id": task_id,
                    "outcome": str(run.get("outcome", "error")),
                    "telemetry": run.get("telemetry")
                    if isinstance(run.get("telemetry"), dict)
                    else {
                        "execution_lane": ("lab" if str(args.runtime_target).strip().lower() in {"lab", "gpu", "selfhosted"} else "ci"),
                        "vram_profile": (str(os.environ.get("ORKET_VRAM_PROFILE", "")).strip() or "safe"),
                        "init_latency": None,
                        "total_latency": _round3(float(run.get("duration_ms", 0.0) or 0.0) / 1000.0),
                        "peak_memory_rss": 0.0,
                        "adherence_score": None,
                        "internal_model_seconds": None,
                        "orchestration_overhead_ratio": None,
                        "run_quality_status": "POLLUTED",
                        "run_quality_reasons": ["MISSING_EXPERIMENTAL_CONTROLS", "MISSING_TOKEN_TIMINGS"],
                        "system_load_start": {},
                        "system_load_end": {},
                        "experimental_controls": {
                            "seed": int(args.seed) if int(args.seed) > 0 else None,
                            "threads": int(args.threads) if int(args.threads) > 0 else None,
                            "affinity_policy": str(args.affinity_policy),
                            "warmup_steps": int(args.warmup_steps) if int(args.warmup_steps) > 0 else None,
                        },
                        "token_metrics_status": "TOKEN_AND_TIMING_UNAVAILABLE",
                        "token_metrics": {
                            "status": "TOKEN_AND_TIMING_UNAVAILABLE",
                            "counts": {
                                "prompt_tokens": None,
                                "output_tokens": None,
                                "total_tokens": None,
                            },
                            "latencies": {
                                "prefill_seconds": None,
                                "decode_seconds": None,
                                "total_turn_seconds": _round3(float(run.get("duration_ms", 0.0) or 0.0) / 1000.0),
                            },
                            "throughput": {
                                "prompt_tokens_per_second": None,
                                "generation_tokens_per_second": None,
                            },
                            "audit": {
                                "raw_usage": {},
                                "raw_timings": {},
                            },
                        },
                        "vibe_metrics": {
                            "latency_variance": None,
                            "code_density": 0.0,
                            "gen_retries": 0,
                            "vibe_delta": None,
                            "vibe_delta_status": "NO_BASELINE",
                        },
                    },
                }
            )

    total_tasks = len(tasks)
    report: dict[str, Any] = {
        "schema_version": "1.1.3",
        "report_generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "test_runs": test_runs,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "task_bank": str(task_bank_path).replace("\\", "/"),
        "runtime_target": str(args.runtime_target),
        "execution_mode": str(args.execution_mode),
        "venue": str(args.runtime_target),
        "flow": str(args.execution_mode),
        "runs_per_task": int(args.runs),
        "runner_template": str(args.runner_template),
        "artifact_globs": list(args.artifact_glob),
        "task_id_min": int(args.task_id_min),
        "task_id_max": int(args.task_id_max),
        "experimental_controls": {
            "seed": int(args.seed) if int(args.seed) > 0 else None,
            "threads": int(args.threads) if int(args.threads) > 0 else None,
            "affinity_policy": str(args.affinity_policy),
            "warmup_steps": int(args.warmup_steps) if int(args.warmup_steps) > 0 else None,
        },
        "total_tasks": total_tasks,
        "deterministic_tasks": deterministic_count,
        "determinism_rate": (deterministic_count / total_tasks) if total_tasks else 0.0,
        "avg_latency_ms": round(sum(latency_samples) / len(latency_samples), 3) if latency_samples else 0.0,
        "avg_cost_usd": round(sum(cost_samples) / len(cost_samples), 6) if cost_samples else 0.0,
        "details": details,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
