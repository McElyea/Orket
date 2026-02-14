from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from orket.runtime_paths import resolve_live_acceptance_db_path
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
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
    cur.execute("PRAGMA table_info(live_acceptance_runs)")
    columns = {row[1] for row in cur.fetchall()}
    has_chain_complete = "chain_complete" in columns
    select_chain = ", chain_complete" if has_chain_complete else ""
    cur.execute(
        f"""
        SELECT model, iteration, passed, session_status, metrics_json, db_summary_json{select_chain}
        FROM live_acceptance_runs
        WHERE batch_id = ?
        ORDER BY id
        """,
        (batch_id,),
    )
    runs: List[Dict[str, Any]] = []
    for row in cur.fetchall():
        model, iteration, passed, session_status, metrics_raw, db_summary_raw = row[:6]
        chain_complete = bool(row[6]) if has_chain_complete and len(row) > 6 else None
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
                "chain_complete": chain_complete,
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
        stats = summary.setdefault(
            model,
            {
                "runs": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "chain_complete": 0,
                "chain_incomplete": 0,
            },
        )
        stats["runs"] += 1
        status = run.get("session_status", "")
        canonical_success = bool(run.get("passed")) and run.get("chain_complete") is True
        if str(status).startswith("skipped_"):
            stats["skipped"] += 1
        elif canonical_success:
            stats["passed"] += 1
        else:
            stats["failed"] += 1
        chain_complete = run.get("chain_complete")
        if chain_complete is True:
            stats["chain_complete"] += 1
        elif chain_complete is False:
            stats["chain_incomplete"] += 1
    return summary


def _chain_mismatch_count(runs: List[Dict[str, Any]]) -> int:
    mismatches = 0
    for run in runs:
        if run.get("session_status") == "done" and run.get("chain_complete") is False:
            mismatches += 1
    return mismatches


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


def _model_compliance_summary(runs: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    summary: Dict[str, Dict[str, Any]] = {}
    for run in runs:
        model = str(run.get("model") or "unknown")
        metrics = run.get("metrics", {}) if isinstance(run.get("metrics"), dict) else {}
        item = summary.setdefault(
            model,
            {
                "runs": 0,
                "hallucination_violation_runs": 0,
                "security_violation_runs": 0,
                "consistency_violation_runs": 0,
                "retries_total": 0,
                "terminal_failure_runs": 0,
                "guard_pass_runs": 0,
            },
        )
        item["runs"] += 1
        if int(metrics.get("turn_non_progress_hallucination_scope", 0) or 0) > 0:
            item["hallucination_violation_runs"] += 1
        if int(metrics.get("turn_non_progress_security_scope", 0) or 0) > 0:
            item["security_violation_runs"] += 1
        if int(metrics.get("turn_non_progress_consistency_scope", 0) or 0) > 0:
            item["consistency_violation_runs"] += 1
        item["retries_total"] += int(metrics.get("guard_retry_scheduled", 0) or 0)
        if str(run.get("session_status") or "") == "terminal_failure" or int(
            metrics.get("guard_terminal_failure", 0) or 0
        ) > 0:
            item["terminal_failure_runs"] += 1
        if bool(run.get("passed")) and run.get("chain_complete") is True:
            item["guard_pass_runs"] += 1

    for model, item in summary.items():
        n = max(1, int(item["runs"]))
        hallucination_rate = item["hallucination_violation_runs"] / n
        security_rate = item["security_violation_runs"] / n
        consistency_rate = item["consistency_violation_runs"] / n
        avg_retries = item["retries_total"] / n
        terminal_failure_rate = item["terminal_failure_runs"] / n
        guard_pass_rate = item["guard_pass_runs"] / n

        max_retries_cap = 2.0
        score = 100.0
        score -= 0.3 * hallucination_rate * 100.0
        score -= 0.3 * security_rate * 100.0
        score -= 0.1 * consistency_rate * 100.0
        score -= 0.1 * min(1.0, avg_retries / max_retries_cap) * 100.0
        score -= 0.2 * terminal_failure_rate * 100.0
        score = max(0.0, round(score, 2))

        item["hallucination_rate"] = hallucination_rate
        item["security_violation_rate"] = security_rate
        item["consistency_violation_rate"] = consistency_rate
        item["avg_retries"] = avg_retries
        item["terminal_failure_rate"] = terminal_failure_rate
        item["guard_pass_rate"] = guard_pass_rate
        item["compliance_score"] = score
    return summary


def _build_report(batch_id: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "batch_id": batch_id,
        "run_count": len(runs),
        "session_status_counts": _status_counts(runs),
        "completion_by_model": _completion_by_model(runs),
        "model_compliance": _model_compliance_summary(runs),
        "pattern_counters": {
            "turn_corrective_reprompt": _sum_metric(runs, "turn_corrective_reprompt"),
            "turn_non_progress": _sum_metric(runs, "turn_non_progress"),
            "dependency_block_propagated": _sum_metric(runs, "dependency_block_propagated"),
            "tool_call_blocked": _sum_metric(runs, "tool_call_blocked"),
            "runtime_verifier_started": _sum_metric(runs, "runtime_verifier_started"),
            "runtime_verifier_completed": _sum_metric(runs, "runtime_verifier_completed"),
            "runtime_verifier_failures": _sum_metric(runs, "runtime_verifier_failures"),
            "runtime_verifier_failure_python_compile": _sum_metric(runs, "runtime_verifier_failure_python_compile"),
            "runtime_verifier_failure_timeout": _sum_metric(runs, "runtime_verifier_failure_timeout"),
            "runtime_verifier_failure_command_failed": _sum_metric(runs, "runtime_verifier_failure_command_failed"),
            "runtime_verifier_failure_missing_runtime": _sum_metric(runs, "runtime_verifier_failure_missing_runtime"),
            "runtime_verifier_failure_deployment_missing": _sum_metric(runs, "runtime_verifier_failure_deployment_missing"),
            "guard_retry_scheduled": _sum_metric(runs, "guard_retry_scheduled"),
            "guard_terminal_failure": _sum_metric(runs, "guard_terminal_failure"),
            "guard_terminal_reason_hallucination_persistent": _sum_metric(
                runs, "guard_terminal_reason_hallucination_persistent"
            ),
            "turn_non_progress_hallucination_scope": _sum_metric(runs, "turn_non_progress_hallucination_scope"),
            "turn_non_progress_security_scope": _sum_metric(runs, "turn_non_progress_security_scope"),
            "turn_non_progress_consistency_scope": _sum_metric(runs, "turn_non_progress_consistency_scope"),
            "prompt_turn_start_total": _sum_metric(runs, "prompt_turn_start_total"),
            "prompt_resolver_policy_compiler": _sum_metric(runs, "prompt_resolver_policy_compiler"),
            "prompt_resolver_policy_resolver_v1": _sum_metric(runs, "prompt_resolver_policy_resolver_v1"),
            "prompt_selection_policy_stable": _sum_metric(runs, "prompt_selection_policy_stable"),
            "prompt_selection_policy_canary": _sum_metric(runs, "prompt_selection_policy_canary"),
            "prompt_selection_policy_exact": _sum_metric(runs, "prompt_selection_policy_exact"),
            "runtime_event_envelope_count": _sum_metric(runs, "runtime_event_envelope_count"),
            "runtime_event_schema_v1_count": _sum_metric(runs, "runtime_event_schema_v1_count"),
            "done_chain_mismatch": _chain_mismatch_count(runs),
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
