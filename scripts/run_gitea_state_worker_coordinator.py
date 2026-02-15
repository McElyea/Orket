from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.runtime_policy import (
    resolve_gitea_worker_max_duration_seconds,
    resolve_gitea_worker_max_idle_streak,
    resolve_gitea_worker_max_iterations,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from orket.application.services.gitea_state_worker_coordinator import GiteaStateWorkerCoordinator


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the experimental gitea state worker coordinator loop."
    )
    parser.add_argument("--worker-id", default="", help="Worker identifier. Defaults to host-pid.")
    parser.add_argument("--fetch-limit", type=int, default=5, help="Fetch limit per run_once cycle.")
    parser.add_argument("--lease-seconds", type=int, default=30, help="Lease duration in seconds.")
    parser.add_argument(
        "--renew-interval-seconds",
        type=float,
        default=5.0,
        help="Lease renew heartbeat interval in seconds.",
    )
    parser.add_argument("--max-iterations", type=int, default=None, help="Maximum coordinator iterations.")
    parser.add_argument("--max-idle-streak", type=int, default=None, help="Maximum consecutive idle iterations.")
    parser.add_argument(
        "--max-duration-seconds",
        type=float,
        default=None,
        help="Maximum coordinator runtime in seconds.",
    )
    parser.add_argument(
        "--idle-sleep-seconds",
        type=float,
        default=0.0,
        help="Optional sleep between idle iterations.",
    )
    parser.add_argument(
        "--summary-out",
        default="benchmarks/results/gitea_state_worker_run_summary.json",
        help="Run summary JSON artifact path.",
    )
    parser.add_argument(
        "--allow-mutate",
        action="store_true",
        help="Required flag. Acknowledge that this loop transitions issue states in gitea.",
    )
    return parser.parse_args()


def _required_env(name: str) -> str:
    value = str(os.environ.get(name) or "").strip()
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


def _resolve_worker_id(raw: str) -> str:
    value = str(raw or "").strip()
    if value:
        return value
    return f"{socket.gethostname()}-{os.getpid()}"


async def _run_loop(args: argparse.Namespace) -> Dict[str, Any]:
    readiness = evaluate_gitea_state_pilot_readiness(collect_gitea_state_pilot_inputs())
    if not bool(readiness.get("ready")):
        failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
        raise RuntimeError(f"gitea state pilot readiness failed: {failures}")

    max_iterations = resolve_gitea_worker_max_iterations(
        args.max_iterations,
        os.environ.get("ORKET_GITEA_WORKER_MAX_ITERATIONS"),
    )
    max_idle_streak = resolve_gitea_worker_max_idle_streak(
        args.max_idle_streak,
        os.environ.get("ORKET_GITEA_WORKER_MAX_IDLE_STREAK"),
    )
    max_duration_seconds = resolve_gitea_worker_max_duration_seconds(
        args.max_duration_seconds,
        os.environ.get("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS"),
    )

    adapter = GiteaStateAdapter(
        base_url=_required_env("ORKET_GITEA_URL"),
        token=_required_env("ORKET_GITEA_TOKEN"),
        owner=_required_env("ORKET_GITEA_OWNER"),
        repo=_required_env("ORKET_GITEA_REPO"),
    )
    worker_id = _resolve_worker_id(args.worker_id)
    worker = GiteaStateWorker(
        adapter=adapter,
        worker_id=worker_id,
        lease_seconds=args.lease_seconds,
        renew_interval_seconds=args.renew_interval_seconds,
    )
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        fetch_limit=args.fetch_limit,
        max_iterations=max_iterations,
        max_idle_streak=max_idle_streak,
        max_duration_seconds=max_duration_seconds,
        idle_sleep_seconds=args.idle_sleep_seconds,
    )

    async def _work_fn(_card: Dict[str, Any]) -> Dict[str, Any]:
        return {"result": "ok"}

    summary = await coordinator.run(work_fn=_work_fn)
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "worker_id": worker_id,
        "fetch_limit": max(1, int(args.fetch_limit)),
        "max_iterations": max_iterations,
        "max_idle_streak": max_idle_streak,
        "max_duration_seconds": max_duration_seconds,
        "summary": summary,
    }


def main() -> int:
    args = _parse_args()
    if not bool(args.allow_mutate):
        print(
            json.dumps(
                {
                    "ready": False,
                    "error": "--allow-mutate is required to run this experimental loop",
                },
                indent=2,
            )
        )
        return 2

    try:
        payload = asyncio.run(_run_loop(args))
    except Exception as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, indent=2))
        return 1

    out_path = Path(args.summary_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
