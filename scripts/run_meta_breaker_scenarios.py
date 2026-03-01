from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.extensions import ExtensionManager


SCENARIOS = [
    {
        "scenario_id": "first_player_low",
        "seed": 21,
        "first_player_advantage": 0.01,
        "dominant_threshold": 0.55,
    },
    {
        "scenario_id": "first_player_high",
        "seed": 21,
        "first_player_advantage": 0.08,
        "dominant_threshold": 0.55,
    },
    {
        "scenario_id": "strict_balance_gate",
        "seed": 34,
        "first_player_advantage": 0.02,
        "dominant_threshold": 0.52,
    },
]


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    manager = ExtensionManager(project_root=Path(args.project_root).resolve())
    workspace = Path(args.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    scenario_rows: list[dict[str, Any]] = []
    for row in SCENARIOS:
        result = await manager.run_workload(
            workload_id="meta_breaker_v1",
            input_config={
                "seed": int(row["seed"]),
                "first_player_advantage": float(row["first_player_advantage"]),
                "dominant_threshold": float(row["dominant_threshold"]),
            },
            workspace=workspace,
            department=args.department,
        )
        output = result.summary.get("output") if isinstance(result.summary, dict) else {}
        findings = output.get("findings") if isinstance(output, dict) else {}
        dominant = findings.get("dominant_archetypes") if isinstance(findings, dict) else []
        scenario_rows.append(
            {
                "scenario_id": row["scenario_id"],
                "plan_hash": result.plan_hash,
                "balance_status": str(findings.get("balance_status") if isinstance(findings, dict) else "unknown"),
                "dominant_archetypes": list(dominant) if isinstance(dominant, list) else [],
                "artifact_root": result.artifact_root,
                "provenance_path": result.provenance_path,
            }
        )

    return {
        "schema_version": "meta_breaker.scenario_pack.v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "workload_id": "meta_breaker_v1",
        "scenario_count": len(scenario_rows),
        "scenarios": scenario_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run predefined Meta Breaker scenario pack.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--workspace", default="workspace/default")
    parser.add_argument("--department", default="core")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    payload = asyncio.run(_run(args))
    output = str(args.output or "").strip()
    if output:
        out_path = Path(output).resolve()
    else:
        out_path = Path(args.project_root).resolve() / "workspace" / "diagnostics" / "meta_breaker_scenario_pack.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
