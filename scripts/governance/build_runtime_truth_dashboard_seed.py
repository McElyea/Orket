from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build runtime truth dashboard seed metrics from run ledger data.")
    parser.add_argument("--db-path", required=True, help="Path to runtime sqlite db containing run_ledger table.")
    return parser.parse_args(argv)


def _load_run_rows(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        raise ValueError(f"E_RUNTIME_TRUTH_DASHBOARD_DB_MISSING:{db_path}")
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """
            SELECT session_id, status, failure_class, failure_reason, summary_json, artifact_json
            FROM run_ledger
            """
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def _json_dict(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def build_runtime_truth_dashboard_seed(*, db_path: Path) -> dict[str, Any]:
    rows = _load_run_rows(db_path)
    total_runs = len(rows)
    status_counts: dict[str, int] = {}
    timeout_signals = 0
    invalid_payload_signals = 0
    fallback_signals = 0
    repair_signals = 0
    silent_degrade_signals = 0

    for row in rows:
        status = str(row.get("status") or "").strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        failure_reason = str(row.get("failure_reason") or "").strip().lower()
        failure_class = str(row.get("failure_class") or "").strip()
        summary = _json_dict(row.get("summary_json"))
        artifacts = _json_dict(row.get("artifact_json"))

        if "timeout" in failure_reason:
            timeout_signals += 1
        if any(token in failure_reason for token in ("parse", "schema", "invalid", "json")):
            invalid_payload_signals += 1
        if "repair" in failure_reason:
            repair_signals += 1

        route_decision = artifacts.get("route_decision_artifact")
        reason_code = ""
        if isinstance(route_decision, dict):
            reason_code = str(route_decision.get("reason_code") or "").strip().lower()
        if status in {"degraded", "incomplete"} or reason_code == "resume_stalled_issues":
            fallback_signals += 1

        session_status = str(summary.get("session_status") or "").strip().lower()
        if status == "incomplete" and not failure_class and not failure_reason and session_status == "incomplete":
            silent_degrade_signals += 1

    denominator = total_runs if total_runs > 0 else 1
    return {
        "schema_version": "runtime_truth_dashboard_seed.v1",
        "observed_path": "primary",
        "result": "success",
        "counts": {
            "runs_total": total_runs,
            "status_counts": status_counts,
            "fallback_signals": fallback_signals,
            "repair_signals": repair_signals,
            "invalid_payload_signals": invalid_payload_signals,
            "timeout_signals": timeout_signals,
            "silent_degrade_signals": silent_degrade_signals,
        },
        "rates": {
            "fallback_signal_rate": fallback_signals / denominator,
            "repair_signal_rate": repair_signals / denominator,
            "invalid_payload_signal_rate": invalid_payload_signals / denominator,
            "timeout_signal_rate": timeout_signals / denominator,
            "silent_degrade_signal_rate": silent_degrade_signals / denominator,
        },
        "notes": [
            "Seed metrics are heuristic until dedicated fallback/repair ledgers are promoted.",
            "Counts are derived from run_ledger status/failure and artifact summaries.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv or [])
        payload = build_runtime_truth_dashboard_seed(db_path=Path(args.db_path).resolve())
    except ValueError as exc:
        payload = {
            "schema_version": "runtime_truth_dashboard_seed.v1",
            "observed_path": "blocked",
            "result": "failure",
            "error": str(exc),
        }
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        return 1

    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
