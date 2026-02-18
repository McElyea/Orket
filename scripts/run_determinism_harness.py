from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run benchmark tasks repeatedly and report output drift.")
    parser.add_argument("--task-bank", default="benchmarks/task_bank/v1/tasks.json")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--venue", default="standard")
    parser.add_argument("--flow", default="default")
    parser.add_argument("--output", default="benchmarks/results/determinism_report.json")
    parser.add_argument(
        "--runner-template",
        default="orket run --task {task_file} --venue {venue} --flow {flow}",
        help="Command template placeholders: {task_file}, {venue}, {flow}, {run_dir}, {repo_root}, {workdir}.",
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


def _run_once(
    task: dict[str, Any],
    run_index: int,
    venue: str,
    flow: str,
    runner_template: str,
    artifact_globs: list[str],
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="orket_det_") as temp_dir:
        run_dir = Path(temp_dir)
        task_file = run_dir / "task.json"
        task_file.write_text(json.dumps(task, indent=2), encoding="utf-8")

        command = runner_template.format(
            task_file=str(task_file),
            venue=venue,
            flow=flow,
            workdir=str(run_dir),
            run_dir=str(run_dir),
            repo_root=str(repo_root),
        )

        env = os.environ.copy()
        started = time.perf_counter()
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            check=False,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw_output = (result.stdout or "") + "\n" + (result.stderr or "")

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
            "hash": digest,
            "duration_ms": elapsed_ms,
            "cost_usd": 0.0,
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
    for task in tasks:
        task_id = str(task.get("id", "unknown"))
        runs = [
            _run_once(
                task=task,
                run_index=index + 1,
                venue=str(args.venue),
                flow=str(args.flow),
                runner_template=str(args.runner_template),
                artifact_globs=list(args.artifact_glob),
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

    total_tasks = len(tasks)
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "task_bank": str(task_bank_path).replace("\\", "/"),
        "venue": str(args.venue),
        "flow": str(args.flow),
        "runs_per_task": int(args.runs),
        "runner_template": str(args.runner_template),
        "artifact_globs": list(args.artifact_glob),
        "task_id_min": int(args.task_id_min),
        "task_id_max": int(args.task_id_max),
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
