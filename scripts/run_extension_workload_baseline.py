from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.extensions import ExtensionManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an extension workload repeatedly and emit latency baseline artifacts.")
    parser.add_argument("--repo", default="", help="Optional extension repo path/url to install before running.")
    parser.add_argument("--workload-id", required=True, help="Workload id to execute.")
    parser.add_argument("--runs", type=int, default=5, help="Number of repeated runs.")
    parser.add_argument("--seed", type=int, default=1, help="Seed value included in input_config.")
    parser.add_argument("--department", default="core")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--workspace", default="workspace/default")
    parser.add_argument("--input-json", default="", help="Optional JSON file merged into input_config.")
    parser.add_argument("--output", default="", help="Optional report output path.")
    return parser.parse_args()


def _load_input_payload(path: str) -> dict[str, Any]:
    value = str(path or "").strip()
    if not value:
        return {}
    payload = json.loads(Path(value).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("--input-json must contain a JSON object")
    return payload


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = rank - lower
    return round((ordered[lower] * (1.0 - weight)) + (ordered[upper] * weight), 3)


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    project_root = Path(args.project_root).resolve()
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    manager = ExtensionManager(project_root=project_root)
    if str(args.repo or "").strip():
        manager.install_from_repo(str(args.repo).strip())

    input_payload = _load_input_payload(str(args.input_json))
    input_config = {"seed": int(args.seed), **input_payload}
    run_rows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    for index in range(int(args.runs)):
        started = time.perf_counter()
        result = await manager.run_workload(
            workload_id=str(args.workload_id),
            input_config=dict(input_config),
            workspace=workspace,
            department=str(args.department),
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        latencies_ms.append(elapsed_ms)
        run_rows.append(
            {
                "run_index": index + 1,
                "latency_ms": elapsed_ms,
                "plan_hash": result.plan_hash,
                "artifact_root": result.artifact_root,
                "provenance_path": result.provenance_path,
            }
        )

    report = {
        "schema_version": "extension_workload_baseline.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "project_root": str(project_root),
        "workspace": str(workspace),
        "workload_id": str(args.workload_id),
        "runs": int(args.runs),
        "input_config": input_config,
        "latency_ms": {
            "min": round(min(latencies_ms), 3) if latencies_ms else 0.0,
            "max": round(max(latencies_ms), 3) if latencies_ms else 0.0,
            "mean": round(statistics.fmean(latencies_ms), 3) if latencies_ms else 0.0,
            "p50": _percentile(latencies_ms, 50.0),
            "p95": _percentile(latencies_ms, 95.0),
        },
        "run_rows": run_rows,
    }
    return report


def main() -> int:
    args = _parse_args()
    report = asyncio.run(_run(args))
    output = str(args.output or "").strip()
    if output:
        out_path = Path(output).resolve()
    else:
        out_path = (Path(args.project_root).resolve() / "workspace" / "diagnostics" / f"baseline_{args.workload_id}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
