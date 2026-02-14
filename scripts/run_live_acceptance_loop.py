from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from orket.runtime_paths import resolve_live_acceptance_db_path

DEFAULT_TEST = (
    "tests/live/test_system_acceptance_pipeline.py::"
    "test_system_acceptance_role_pipeline_with_guard_live"
)


@dataclass
class RunSpec:
    model: str
    iteration: int
    run_dir: Path


ROLE_TO_ISSUE_ID = {
    "requirements_analyst": "REQ-1",
    "architect": "ARC-1",
    "coder": "COD-1",
    "code_reviewer": "REV-1",
}

ROLE_TO_TURN_METRIC = {
    "requirements_analyst": "requirements_turn_complete",
    "architect": "architect_turn_complete",
    "coder": "coder_turn_complete",
    "code_reviewer": "reviewer_turn_complete",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def _safe_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return

    def _onerror(func, failed_path, _exc_info):
        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    shutil.rmtree(path, onerror=_onerror)


def _parse_json_lines(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    for line in _safe_read_text(path).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _event_count(events: List[Dict[str, Any]], event_name: str, role: Optional[str] = None) -> int:
    count = 0
    for event in events:
        if event.get("event") != event_name:
            continue
        if role is not None and event.get("role") != role:
            continue
        count += 1
    return count


def _event_count_with_flag(events: List[Dict[str, Any]], event_name: str, data_flag: str, expected: Any) -> int:
    count = 0
    for event in events:
        if event.get("event") != event_name:
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        if data.get(data_flag) == expected:
            count += 1
    return count


def _runtime_failure_breakdown_count(events: List[Dict[str, Any]], failure_class: str) -> int:
    total = 0
    for event in events:
        if event.get("event") != "runtime_verifier_completed":
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        breakdown = data.get("failure_breakdown")
        if not isinstance(breakdown, dict):
            continue
        value = breakdown.get(failure_class, 0)
        if isinstance(value, int):
            total += value
    return total


def _event_reason_contains_count(events: List[Dict[str, Any]], event_name: str, needle: str) -> int:
    target = str(needle or "").strip().lower()
    if not target:
        return 0
    count = 0
    for event in events:
        if event.get("event") != event_name:
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        reason = str(data.get("reason", "") or "").strip().lower()
        if target in reason:
            count += 1
    return count


def _guard_terminal_reason_count(events: List[Dict[str, Any]], terminal_reason_code: str) -> int:
    target = str(terminal_reason_code or "").strip().upper()
    if not target:
        return 0
    count = 0
    for event in events:
        if event.get("event") != "guard_terminal_failure":
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        guard_decision = data.get("guard_decision")
        code = ""
        if isinstance(guard_decision, dict):
            terminal_reason = guard_decision.get("terminal_reason")
            if isinstance(terminal_reason, dict):
                code = str(terminal_reason.get("code", "") or "").strip().upper()
        if code == target:
            count += 1
    return count


def _runtime_event_presence_count(events: List[Dict[str, Any]]) -> int:
    count = 0
    for event in events:
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        runtime_event = data.get("runtime_event")
        if isinstance(runtime_event, dict):
            count += 1
    return count


def _runtime_event_schema_version_count(events: List[Dict[str, Any]], schema_version: str) -> int:
    target = str(schema_version or "").strip()
    if not target:
        return 0
    count = 0
    for event in events:
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        runtime_event = data.get("runtime_event")
        if not isinstance(runtime_event, dict):
            continue
        if str(runtime_event.get("schema_version") or "").strip() == target:
            count += 1
    return count


def _last_event_data(events: List[Dict[str, Any]], event_name: str) -> Dict[str, Any]:
    for event in reversed(events):
        if event.get("event") == event_name:
            data = event.get("data")
            if isinstance(data, dict):
                return data
            return {}
    return {}


def _prompt_policy_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    resolver_policy_counts: Dict[str, int] = {}
    selection_policy_counts: Dict[str, int] = {}
    role_status_counts: Dict[str, int] = {}
    dialect_status_counts: Dict[str, int] = {}
    turn_start_count = 0

    for event in events:
        if event.get("event") != "turn_start":
            continue
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        turn_start_count += 1
        resolver_policy = str(data.get("resolver_policy") or "unknown").strip() or "unknown"
        selection_policy = str(data.get("selection_policy") or "unknown").strip() or "unknown"
        role_status = str(data.get("role_status") or "unknown").strip() or "unknown"
        dialect_status = str(data.get("dialect_status") or "unknown").strip() or "unknown"
        resolver_policy_counts[resolver_policy] = resolver_policy_counts.get(resolver_policy, 0) + 1
        selection_policy_counts[selection_policy] = selection_policy_counts.get(selection_policy, 0) + 1
        role_status_counts[role_status] = role_status_counts.get(role_status, 0) + 1
        dialect_status_counts[dialect_status] = dialect_status_counts.get(dialect_status, 0) + 1

    return {
        "turn_start_count": turn_start_count,
        "resolver_policy_counts": resolver_policy_counts,
        "selection_policy_counts": selection_policy_counts,
        "role_status_counts": role_status_counts,
        "dialect_status_counts": dialect_status_counts,
    }


def _find_latest(root: Path, filename: str) -> Optional[Path]:
    candidates = list(root.rglob(filename))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _find_orket_log(root: Path) -> Optional[Path]:
    candidates = list(root.rglob("orket.log"))
    if not candidates:
        return None

    def score(path: Path) -> int:
        text = str(path).replace("\\", "/").lower()
        if text.endswith("/workspace/orket.log"):
            return 3
        if "/workspace/default/orket.log" in text:
            return 1
        return 2

    candidates.sort(key=lambda p: (score(p), p.stat().st_mtime), reverse=True)
    return candidates[0]


def _first_requirements_response(root: Path) -> Optional[str]:
    candidates = [
        p
        for p in root.rglob("model_response.txt")
        if "requirements_analyst" in str(p).lower()
    ]
    if not candidates:
        return None
    candidates.sort()
    text = _safe_read_text(candidates[0]).replace("\r", " ").replace("\n", " ")
    return text[:220]


def _sqlite_summary(db_path: Optional[Path]) -> Dict[str, Any]:
    if db_path is None or not db_path.exists():
        return {"exists": False}

    result: Dict[str, Any] = {"exists": True, "path": str(db_path)}
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    result["tables"] = tables

    def _table_exists(name: str) -> bool:
        return name in tables

    if _table_exists("sessions"):
        cur.execute("SELECT id, status, start_time, end_time FROM sessions ORDER BY start_time DESC")
        result["sessions"] = [
            {"id": row[0], "status": row[1], "start_time": row[2], "end_time": row[3]}
            for row in cur.fetchall()
        ]

    if _table_exists("issues"):
        cur.execute(
            "SELECT id, status, assignee, retry_count, max_retries "
            "FROM issues ORDER BY id"
        )
        issues = [
            {
                "id": row[0],
                "status": row[1],
                "assignee": row[2],
                "retry_count": row[3],
                "max_retries": row[4],
            }
            for row in cur.fetchall()
        ]
        result["issues"] = issues
        result["issue_statuses"] = {issue["id"]: issue["status"] for issue in issues}

    if _table_exists("card_transactions"):
        cur.execute("SELECT COUNT(*) FROM card_transactions")
        result["card_transactions_count"] = int(cur.fetchone()[0])

    if _table_exists("success_ledger"):
        cur.execute("SELECT COUNT(*) FROM success_ledger")
        result["success_ledger_count"] = int(cur.fetchone()[0])
    else:
        result["success_ledger_count"] = 0

    conn.close()
    return result


def _run_once(spec: RunSpec, python_exe: str, pytest_target: str) -> Dict[str, Any]:
    if spec.run_dir.exists():
        _safe_rmtree(spec.run_dir)
    spec.run_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["ORKET_LIVE_ACCEPTANCE"] = "1"
    env["ORKET_LIVE_MODEL"] = spec.model
    env.setdefault("ORKET_DISABLE_SANDBOX", "1")

    cmd = [
        python_exe,
        "-m",
        "pytest",
        pytest_target,
        "-q",
        "-s",
        "--basetemp",
        str(spec.run_dir),
    ]

    started = datetime.now(UTC)
    completed = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    finished = datetime.now(UTC)

    stdout_path = spec.run_dir / "run_output.log"
    stderr_path = spec.run_dir / "run_error.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")

    log_path = _find_orket_log(spec.run_dir)
    db_path = _find_latest(spec.run_dir, "acceptance_pipeline_live.db")
    events = _parse_json_lines(log_path) if log_path else []
    db_summary = _sqlite_summary(db_path)
    prompt_policy = _prompt_policy_summary(events)
    session_end = _last_event_data(events, "session_end")
    session_start = _last_event_data(events, "session_start")

    metrics = {
        "turn_corrective_reprompt": _event_count(events, "turn_corrective_reprompt"),
        "turn_non_progress": _event_count(events, "turn_non_progress"),
        "tool_call_blocked": _event_count(events, "tool_call_blocked"),
        "dependency_block_propagated": _event_count(events, "dependency_block_propagated"),
        "orchestrator_stalled": _event_count(events, "orchestrator_stalled"),
        "runtime_verifier_started": _event_count(events, "runtime_verifier_started"),
        "runtime_verifier_completed": _event_count(events, "runtime_verifier_completed"),
        "runtime_verifier_failures": _event_count_with_flag(
            events, "runtime_verifier_completed", "ok", False
        ),
        "runtime_verifier_failure_python_compile": _runtime_failure_breakdown_count(
            events, "python_compile"
        ),
        "runtime_verifier_failure_timeout": _runtime_failure_breakdown_count(
            events, "timeout"
        ),
        "runtime_verifier_failure_command_failed": _runtime_failure_breakdown_count(
            events, "command_failed"
        ),
        "runtime_verifier_failure_missing_runtime": _runtime_failure_breakdown_count(
            events, "missing_runtime"
        ),
        "runtime_verifier_failure_deployment_missing": _runtime_failure_breakdown_count(
            events, "deployment_missing"
        ),
        "guard_retry_scheduled": _event_count(events, "guard_retry_scheduled"),
        "guard_terminal_failure": _event_count(events, "guard_terminal_failure"),
        "guard_terminal_reason_hallucination_persistent": _guard_terminal_reason_count(
            events, "HALLUCINATION_PERSISTENT"
        ),
        "turn_non_progress_hallucination_scope": _event_reason_contains_count(
            events, "turn_non_progress", "hallucination_scope_contract_not_met"
        ),
        "turn_non_progress_security_scope": _event_reason_contains_count(
            events, "turn_non_progress", "security_scope_contract_not_met"
        ),
        "turn_non_progress_consistency_scope": _event_reason_contains_count(
            events, "turn_non_progress", "consistency_scope_contract_not_met"
        ),
        "requirements_turn_complete": _event_count(events, "turn_complete", role="requirements_analyst"),
        "architect_turn_complete": _event_count(events, "turn_complete", role="architect"),
        "coder_turn_complete": _event_count(events, "turn_complete", role="coder"),
        "reviewer_turn_complete": _event_count(events, "turn_complete", role="code_reviewer"),
        "guard_turn_complete": _event_count(events, "turn_complete", role="integrity_guard"),
        "prompt_turn_start_total": int(prompt_policy.get("turn_start_count", 0)),
        "prompt_resolver_policy_compiler": int(
            prompt_policy.get("resolver_policy_counts", {}).get("compiler", 0)
        ),
        "prompt_resolver_policy_resolver_v1": int(
            prompt_policy.get("resolver_policy_counts", {}).get("resolver_v1", 0)
        ),
        "prompt_selection_policy_stable": int(
            prompt_policy.get("selection_policy_counts", {}).get("stable", 0)
        ),
        "prompt_selection_policy_canary": int(
            prompt_policy.get("selection_policy_counts", {}).get("canary", 0)
        ),
        "prompt_selection_policy_exact": int(
            prompt_policy.get("selection_policy_counts", {}).get("exact", 0)
        ),
        "runtime_event_envelope_count": _runtime_event_presence_count(events),
        "runtime_event_schema_v1_count": _runtime_event_schema_version_count(events, "v1"),
    }

    chain_complete = _chain_complete(db_summary)
    return {
        "model": spec.model,
        "iteration": spec.iteration,
        "passed": completed.returncode == 0,
        "exit_code": completed.returncode,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 3),
        "command": cmd,
        "run_dir": str(spec.run_dir),
        "run_output_log": str(stdout_path),
        "run_error_log": str(stderr_path),
        "orket_log": str(log_path) if log_path else None,
        "db_summary": db_summary,
        "run_id": session_start.get("run_id"),
        "session_status": session_end.get("status"),
        "metrics": metrics,
        "prompt_policy_summary": prompt_policy,
        "requirements_response_preview": _first_requirements_response(spec.run_dir),
        "chain_complete": chain_complete,
        "canonical_success": bool(completed.returncode == 0 and chain_complete),
    }


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_model: Dict[str, Dict[str, Any]] = {}
    for result in results:
        model = result["model"]
        model_stats = by_model.setdefault(
            model,
            {"runs": 0, "passed": 0, "failed": 0, "skipped": 0, "avg_duration_s": 0.0},
        )
        model_stats["runs"] += 1
        canonical_success = bool(result.get("passed")) and bool(result.get("chain_complete"))
        if result.get("session_status", "").startswith("skipped_"):
            model_stats["skipped"] += 1
        elif canonical_success:
            model_stats["passed"] += 1
        else:
            model_stats["failed"] += 1
        model_stats["avg_duration_s"] += float(result.get("duration_s", 0.0))

    for stats in by_model.values():
        if stats["runs"] > 0:
            stats["avg_duration_s"] = round(stats["avg_duration_s"] / stats["runs"], 3)

    return by_model


def _list_installed_models() -> set[str]:
    proc = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        return set()

    models: set[str] = set()
    for raw_line in (proc.stdout or "").splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("name "):
            continue
        parts = re.split(r"\s{2,}", line)
        if not parts:
            continue
        model = parts[0].strip()
        if model:
            models.add(model)
    return models


def _make_skipped_result(spec: RunSpec, reason: str) -> Dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "model": spec.model,
        "iteration": spec.iteration,
        "passed": False,
        "exit_code": 0,
        "started_at": now.isoformat(),
        "finished_at": now.isoformat(),
        "duration_s": 0.0,
        "command": [],
        "run_dir": str(spec.run_dir),
        "run_output_log": "",
        "run_error_log": "",
        "orket_log": None,
        "db_summary": {"exists": False},
        "run_id": None,
        "session_status": reason,
        "metrics": {"skipped": 1},
        "prompt_policy_summary": {
            "turn_start_count": 0,
            "resolver_policy_counts": {},
            "selection_policy_counts": {},
            "role_status_counts": {},
            "dialect_status_counts": {},
        },
        "requirements_response_preview": None,
        "chain_complete": False,
        "canonical_success": False,
        "model_policy": "skip",
    }


def _parse_model_list(raw: str) -> List[str]:
    if not raw:
        return []
    parts = [item.strip() for item in raw.split(",")]
    return [item for item in parts if item]


def _policy_for_model(model: str, baseline_models: set[str], quarantine_models: set[str]) -> str:
    if model in quarantine_models:
        return "quarantine"
    if baseline_models:
        if model in baseline_models:
            return "baseline"
        return "out_of_baseline"
    return "exploratory"


def _role_capability_outcomes(db_summary: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    issue_statuses = db_summary.get("issue_statuses", {}) if isinstance(db_summary, dict) else {}
    outcomes: Dict[str, Any] = {}
    for role, issue_id in ROLE_TO_ISSUE_ID.items():
        status = issue_statuses.get(issue_id)
        metric_key = ROLE_TO_TURN_METRIC[role]
        outcomes[role] = {
            "issue_id": issue_id,
            "issue_status": status,
            "done": status == "done",
            "turns": int(metrics.get(metric_key, 0)),
        }
    return outcomes


def _chain_complete(db_summary: Dict[str, Any]) -> bool:
    issue_statuses = db_summary.get("issue_statuses", {}) if isinstance(db_summary, dict) else {}
    required = {"REQ-1", "ARC-1", "COD-1", "REV-1"}
    if not required.issubset(set(issue_statuses.keys())):
        return False
    return all(issue_statuses.get(issue_id) == "done" for issue_id in required)


def _init_results_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS live_acceptance_batches (
            batch_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            models_json TEXT NOT NULL,
            iterations INTEGER NOT NULL,
            pytest_target TEXT NOT NULL,
            base_temp_root TEXT NOT NULL,
            python_executable TEXT NOT NULL,
            summary_json TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS live_acceptance_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            model TEXT NOT NULL,
            iteration INTEGER NOT NULL,
            passed INTEGER NOT NULL,
            exit_code INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            duration_s REAL NOT NULL,
            run_id TEXT,
            session_status TEXT,
            run_dir TEXT NOT NULL,
            run_output_log TEXT NOT NULL,
            run_error_log TEXT NOT NULL,
            orket_log TEXT,
            requirements_response_preview TEXT,
            chain_complete INTEGER NOT NULL DEFAULT 0,
            db_summary_json TEXT NOT NULL,
            metrics_json TEXT NOT NULL,
            command_json TEXT NOT NULL,
            FOREIGN KEY(batch_id) REFERENCES live_acceptance_batches(batch_id)
        )
        """
    )
    cur.execute("PRAGMA table_info(live_acceptance_runs)")
    existing_columns = {row[1] for row in cur.fetchall()}
    if "chain_complete" not in existing_columns:
        cur.execute(
            "ALTER TABLE live_acceptance_runs "
            "ADD COLUMN chain_complete INTEGER NOT NULL DEFAULT 0"
        )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_live_acceptance_runs_batch_id "
        "ON live_acceptance_runs(batch_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_live_acceptance_runs_model "
        "ON live_acceptance_runs(model)"
    )
    conn.commit()
    return conn


def _insert_batch(
    conn: sqlite3.Connection,
    *,
    batch_id: str,
    created_at: str,
    models: List[str],
    iterations: int,
    pytest_target: str,
    base_temp_root: str,
    python_executable: str,
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO live_acceptance_batches (
            batch_id, created_at, models_json, iterations, pytest_target, base_temp_root, python_executable
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            created_at,
            json.dumps(models),
            iterations,
            pytest_target,
            base_temp_root,
            python_executable,
        ),
    )
    conn.commit()


def _insert_run_result(conn: sqlite3.Connection, batch_id: str, result: Dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO live_acceptance_runs (
            batch_id, model, iteration, passed, exit_code, started_at, finished_at, duration_s,
            run_id, session_status, run_dir, run_output_log, run_error_log, orket_log,
            requirements_response_preview, chain_complete, db_summary_json, metrics_json, command_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            result["model"],
            int(result["iteration"]),
            1 if result.get("passed") else 0,
            int(result.get("exit_code", 1)),
            result.get("started_at"),
            result.get("finished_at"),
            float(result.get("duration_s", 0.0)),
            result.get("run_id"),
            result.get("session_status"),
            result.get("run_dir"),
            result.get("run_output_log"),
            result.get("run_error_log"),
            result.get("orket_log"),
            result.get("requirements_response_preview"),
            1 if result.get("chain_complete") else 0,
            json.dumps(result.get("db_summary", {})),
            json.dumps(result.get("metrics", {})),
            json.dumps(result.get("command", [])),
        ),
    )
    conn.commit()


def _complete_batch(
    conn: sqlite3.Connection,
    *,
    batch_id: str,
    completed_at: str,
    summary: Dict[str, Any],
) -> None:
    cur = conn.cursor()
    cur.execute(
        "UPDATE live_acceptance_batches SET completed_at = ?, summary_json = ? WHERE batch_id = ?",
        (completed_at, json.dumps(summary), batch_id),
    )
    conn.commit()


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run live acceptance pytest in a loop and emit per-run metrics + DB summaries."
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=[os.getenv("ORKET_LIVE_MODEL", "qwen2.5-coder:7b")],
        help="One or more Ollama model names.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Iterations per model.",
    )
    parser.add_argument(
        "--pytest-target",
        default=DEFAULT_TEST,
        help="Pytest node id to execute.",
    )
    parser.add_argument(
        "--base-temp-root",
        default=".pytest_live_loop",
        help="Root folder for pytest basetemp runs.",
    )
    parser.add_argument(
        "--results-db",
        default=resolve_live_acceptance_db_path(),
        help="SQLite DB path for persistent loop results.",
    )
    parser.add_argument(
        "--output-json",
        "--output",
        dest="output_json",
        default="",
        help="Optional JSON report output path (disabled by default).",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use.",
    )
    parser.add_argument(
        "--skip-missing-models",
        action="store_true",
        default=True,
        help="Skip models missing from `ollama list` instead of executing failing runs.",
    )
    parser.add_argument(
        "--no-skip-missing-models",
        action="store_false",
        dest="skip_missing_models",
        help="Disable missing-model preflight skipping.",
    )
    parser.add_argument(
        "--baseline-models",
        nargs="+",
        default=_parse_model_list(os.getenv("ORKET_BASELINE_MODELS", "")),
        help="Optional allowlist for canonical flow. If set, non-baseline models are skipped.",
    )
    parser.add_argument(
        "--quarantine-models",
        nargs="+",
        default=_parse_model_list(os.getenv("ORKET_QUARANTINE_MODELS", "")),
        help="Optional denylist for unstable models. Quarantined models are skipped.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    batch_created_at = datetime.now(UTC).isoformat()
    batch_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"

    base_temp_root = Path(args.base_temp_root)
    base_temp_root.mkdir(parents=True, exist_ok=True)

    results_db_path = Path(resolve_live_acceptance_db_path(args.results_db))
    conn = _init_results_db(results_db_path)
    _insert_batch(
        conn,
        batch_id=batch_id,
        created_at=batch_created_at,
        models=args.models,
        iterations=args.iterations,
        pytest_target=args.pytest_target,
        base_temp_root=str(base_temp_root),
        python_executable=args.python,
    )

    results: List[Dict[str, Any]] = []
    total_runs = len(args.models) * args.iterations
    run_no = 0
    installed_models = _list_installed_models() if args.skip_missing_models else set()
    baseline_models = {m.strip() for m in (args.baseline_models or []) if m and m.strip()}
    quarantine_models = {m.strip() for m in (args.quarantine_models or []) if m and m.strip()}

    for model in args.models:
        model_slug = _slug(model)
        for iteration in range(1, args.iterations + 1):
            run_no += 1
            run_dir = base_temp_root / f"{model_slug}_iter{iteration}"
            spec = RunSpec(model=model, iteration=iteration, run_dir=run_dir)
            print(f"[{run_no}/{total_runs}] model={model} iteration={iteration} ...")
            policy = _policy_for_model(model, baseline_models, quarantine_models)
            if policy == "quarantine":
                result = _make_skipped_result(spec, reason="skipped_quarantined_model")
                result["model_policy"] = policy
                print(f"  skipped=True reason=quarantined_model model={model}")
            elif policy == "out_of_baseline":
                result = _make_skipped_result(spec, reason="skipped_out_of_baseline")
                result["model_policy"] = policy
                print(f"  skipped=True reason=out_of_baseline model={model}")
            elif args.skip_missing_models and installed_models and model not in installed_models:
                result = _make_skipped_result(spec, reason="skipped_missing_model")
                result["model_policy"] = policy
                print(f"  skipped=True reason=missing_model model={model}")
            else:
                result = _run_once(spec, python_exe=args.python, pytest_target=args.pytest_target)
                result["model_policy"] = policy
                result["metrics"]["role_capability_outcomes"] = _role_capability_outcomes(
                    result.get("db_summary", {}),
                    result.get("metrics", {}),
                )
            results.append(result)
            _insert_run_result(conn, batch_id, result)

            db_issue_statuses = result.get("db_summary", {}).get("issue_statuses", {})
            policy_counts = (result.get("prompt_policy_summary") or {}).get("selection_policy_counts", {})
            print(
                "  "
                f"passed={result['passed']} "
                f"canonical_success={result.get('canonical_success')} "
                f"chain_complete={result.get('chain_complete')} "
                f"run_id={result.get('run_id')} "
                f"session_status={result.get('session_status')} "
                f"prompt_selection={policy_counts} "
                f"issues={db_issue_statuses}"
            )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "models": args.models,
        "iterations": args.iterations,
        "pytest_target": args.pytest_target,
        "base_temp_root": str(base_temp_root),
        "results": results,
        "summary_by_model": _aggregate(results),
    }

    _complete_batch(
        conn,
        batch_id=batch_id,
        completed_at=datetime.now(UTC).isoformat(),
        summary=report["summary_by_model"],
    )
    conn.close()

    print(f"Results stored: {results_db_path} (batch_id={batch_id})")

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"JSON report written: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
