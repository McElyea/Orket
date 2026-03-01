from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.extensions import ExtensionManager


async def _run(args: argparse.Namespace) -> int:
    manager = ExtensionManager(project_root=Path(args.project_root).resolve())
    result = await manager.run_workload(
        workload_id="meta_breaker_v1",
        input_config={
            "seed": int(args.seed),
            "first_player_advantage": float(args.first_player_advantage),
            "dominant_threshold": float(args.dominant_threshold),
        },
        workspace=Path(args.workspace).resolve(),
        department=args.department,
    )
    print(json.dumps(result.summary, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Meta Breaker workload through ExtensionManager.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--workspace", default="workspace/default")
    parser.add_argument("--department", default="core")
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--first-player-advantage", type=float, default=0.02)
    parser.add_argument("--dominant-threshold", type=float, default=0.55)
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
