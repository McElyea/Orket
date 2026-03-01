from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orket.rulesim.workload import run_rulesim_v0_sync


def _rss_bytes() -> int:
    if os.name != "nt":
        import resource

        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    try:
        import psutil  # type: ignore

        return int(psutil.Process().memory_info().rss)
    except Exception:
        return 0


def main() -> int:
    episodes = 100000
    workspace = Path("workspace/rulesim_perf_baseline")
    out_path = Path("benchmarks/results/rulesim_100k_baseline.json")
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "loop",
        "run_seed": 20260301,
        "episodes": episodes,
        "max_steps": 6,
        "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "none",
        "enforce_contract_checks": True,
    }
    tracemalloc.start()
    t0 = time.perf_counter()
    result = run_rulesim_v0_sync(input_config=config, workspace_path=workspace)
    elapsed = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    payload = {
        "date": "2026-03-01",
        "workload_id": "rulesim_v0",
        "rulesystem_id": "loop",
        "episodes": episodes,
        "elapsed_seconds": round(elapsed, 6),
        "episodes_per_second": round((episodes / elapsed) if elapsed > 0 else 0.0, 3),
        "peak_tracemalloc_bytes": int(peak),
        "rss_bytes": _rss_bytes(),
        "result": result,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
