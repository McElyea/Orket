from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from scripts.streaming.live_consistency_common import to_int
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from live_consistency_common import to_int


def collect_stream_verdict_summary(*, project_root: Path, gate_run_id: str, loops_requested: int) -> dict[str, Any]:
    workspace_root = project_root / "workspace" / "observability" / "stream_scenarios"
    if not gate_run_id or not workspace_root.exists():
        return {
            "gate_run_id": gate_run_id,
            "loops_requested": loops_requested,
            "verdict_files_found": 0,
            "loops_seen_global": [],
            "scenarios": [],
        }

    scenario_entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    pattern = f"*/{gate_run_id}/loop-*/run-*/verdict.json"
    for verdict_path in sorted(workspace_root.glob(pattern)):
        rel = verdict_path.relative_to(workspace_root)
        if len(rel.parts) < 5:
            continue
        scenario_id = rel.parts[0]
        loop_name = rel.parts[2]
        loop_index = to_int(loop_name.replace("loop-", "", 1), default=0)
        payload = json.loads(verdict_path.read_text(encoding="utf-8"))
        observed = payload.get("observed") if isinstance(payload.get("observed"), dict) else {}
        expected = payload.get("expected") if isinstance(payload.get("expected"), dict) else {}
        scenario_entries[scenario_id].append(
            {
                "loop_index": loop_index,
                "run_id": str(payload.get("run_id") or ""),
                "status": str(payload.get("status") or ""),
                "law_checker_passed": bool(payload.get("law_checker_passed")),
                "terminal_event": str(observed.get("terminal_event") or ""),
                "commit_outcome": str(observed.get("commit_outcome") or ""),
                "token_delta_count": to_int(observed.get("token_delta_count"), default=0),
                "min_expected_token_deltas": to_int(expected.get("min_token_deltas"), default=0),
                "verdict_path": str(verdict_path.resolve()),
            }
        )

    scenario_summaries: list[dict[str, Any]] = []
    loops_seen_global: set[int] = set()
    for scenario_id in sorted(scenario_entries.keys()):
        rows = sorted(scenario_entries[scenario_id], key=lambda row: (row["loop_index"], row["run_id"]))
        loops_seen = sorted({to_int(row["loop_index"], default=0) for row in rows if to_int(row["loop_index"], 0) > 0})
        loops_seen_global.update(loops_seen)
        status_counts = Counter(str(row["status"]) for row in rows)
        token_counts = [to_int(row["token_delta_count"], 0) for row in rows]
        scenario_summaries.append(
            {
                "scenario_id": scenario_id,
                "runs": len(rows),
                "loops_seen": loops_seen,
                "status_counts": dict(status_counts),
                "law_checker_failures": sum(1 for row in rows if not bool(row["law_checker_passed"])),
                "terminal_event_values": sorted({str(row["terminal_event"]) for row in rows}),
                "commit_outcome_values": sorted({str(row["commit_outcome"]) for row in rows}),
                "min_expected_token_deltas": max(to_int(row["min_expected_token_deltas"], 0) for row in rows),
                "token_delta_min": min(token_counts) if token_counts else 0,
                "token_delta_max": max(token_counts) if token_counts else 0,
            }
        )

    return {
        "gate_run_id": gate_run_id,
        "loops_requested": loops_requested,
        "verdict_files_found": sum(len(rows) for rows in scenario_entries.values()),
        "loops_seen_global": sorted(loops_seen_global),
        "scenarios": scenario_summaries,
    }
