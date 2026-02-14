from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from orket.runtime_paths import resolve_live_acceptance_db_path

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize repeatable live-acceptance failure patterns from SQLite results."
    )
    parser.add_argument(
        "--db",
        default=resolve_live_acceptance_db_path(),
        help="Path to live acceptance loop SQLite database.",
    )
    parser.add_argument(
        "--batch-id",
        default="",
        help="Optional specific batch id. Defaults to latest completed batch.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional JSON output path.",
    )
    return parser.parse_args()


def _latest_batch_id(conn: sqlite3.Connection) -> Optional[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT batch_id
        FROM live_acceptance_batches
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return row[0] if row else None


def _load_runs(conn: sqlite3.Connection, batch_id: str) -> List[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT model, iteration, passed, session_status, metrics_json, db_summary_json
        FROM live_acceptance_runs
        WHERE batch_id = ?
        ORDER BY id
        """,
        (batch_id,),
    )
    runs: List[Dict[str, Any]] = []
    for model, iteration, passed, session_status, metrics_raw, db_summary_raw in cur.fetchall():
        try:
            metrics = json.loads(metrics_raw or "{}")
        except json.JSONDecodeError:
            metrics = {}
        try:
            db_summary = json.loads(db_summary_raw or "{}")
        except json.JSONDecodeError:
            db_summary = {}
        runs.append(
            {
                "model": model,
                "iteration": int(iteration),
                "passed": bool(passed),
                "session_status": session_status or "",
                "metrics": metrics if isinstance(metrics, dict) else {},
                "db_summary": db_summary if isinstance(db_summary, dict) else {},
            }
        )
    return runs


def _sum_metric(runs: List[Dict[str, Any]], key: str) -> int:
    total = 0
    for run in runs:
        value = run.get("metrics", {}).get(key, 0)
        if isinstance(value, int):
            total += value
    return total


def _status_counts(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for run in runs:
        status = run.get("session_status") or "unknown"
        counts[status] = counts.get(status, 0) + 1
    return counts


def _completion_by_model(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for run in runs:
        model = run["model"]
        stats = summary.setdefault(model, {"runs": 0, "passed": 0, "failed": 0, "skipped": 0})
        stats["runs"] += 1
        status = run.get("session_status", "")
        if str(status).startswith("skipped_"):
            stats["skipped"] += 1
        elif run.get("passed"):
            stats["passed"] += 1
        else:
            stats["failed"] += 1
    return summary


def _issue_end_states(runs: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for run in runs:
        statuses = run.get("db_summary", {}).get("issue_statuses", {})
        if not isinstance(statuses, dict):
            continue
        for _issue_id, status in statuses.items():
            key = str(status)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _build_report(batch_id: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "batch_id": batch_id,
        "run_count": len(runs),
        "session_status_counts": _status_counts(runs),
        "completion_by_model": _completion_by_model(runs),
        "pattern_counters": {
            "turn_corrective_reprompt": _sum_metric(runs, "turn_corrective_reprompt"),
            "turn_non_progress": _sum_metric(runs, "turn_non_progress"),
            "dependency_block_propagated": _sum_metric(runs, "dependency_block_propagated"),
            "tool_call_blocked": _sum_metric(runs, "tool_call_blocked"),
        },
        "issue_status_totals": _issue_end_states(runs),
    }


def main() -> int:
    args = _parse_args()
    db_path = Path(resolve_live_acceptance_db_path(args.db))
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        batch_id = args.batch_id.strip() or _latest_batch_id(conn)
        if not batch_id:
            raise SystemExit("No batches found in live acceptance DB.")
        runs = _load_runs(conn, batch_id)
    finally:
        conn.close()

    report = _build_report(batch_id, runs)
    pretty = json.dumps(report, indent=2)
    print(pretty)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(pretty, encoding="utf-8")
        print(f"Report written: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
