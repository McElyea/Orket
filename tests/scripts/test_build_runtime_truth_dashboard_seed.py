from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.governance.build_runtime_truth_dashboard_seed import (
    build_runtime_truth_dashboard_seed,
    main,
)


def _seed_run_ledger(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE run_ledger (
                session_id TEXT PRIMARY KEY,
                status TEXT,
                failure_class TEXT,
                failure_reason TEXT,
                summary_json TEXT,
                artifact_json TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO run_ledger (session_id, status, failure_class, failure_reason, summary_json, artifact_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "run-timeout",
                "failed",
                "ExecutionFailed",
                "provider timeout while waiting",
                json.dumps({"session_status": "failed"}),
                json.dumps({"route_decision_artifact": {"reason_code": "default_epic_route"}}),
            ),
        )
        conn.execute(
            """
            INSERT INTO run_ledger (session_id, status, failure_class, failure_reason, summary_json, artifact_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "run-incomplete",
                "incomplete",
                None,
                None,
                json.dumps({"session_status": "incomplete"}),
                json.dumps({"route_decision_artifact": {"reason_code": "resume_stalled_issues"}}),
            ),
        )
        conn.commit()


# Layer: integration
def test_build_runtime_truth_dashboard_seed_computes_expected_signal_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_run_ledger(db_path)
    payload = build_runtime_truth_dashboard_seed(db_path=db_path)
    assert payload["result"] == "success"
    assert payload["counts"]["runs_total"] == 2
    assert payload["counts"]["timeout_signals"] == 1
    assert payload["counts"]["fallback_signals"] == 1
    assert payload["counts"]["silent_degrade_signals"] == 1


# Layer: contract
def test_build_runtime_truth_dashboard_seed_main_fails_when_db_missing(tmp_path: Path) -> None:
    exit_code = main(["--db-path", str(tmp_path / "missing.db")])
    assert exit_code == 1


# Layer: integration
def test_build_runtime_truth_dashboard_seed_main_uses_sys_argv_when_not_provided(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "runtime.db"
    _seed_run_ledger(db_path)
    monkeypatch.setattr("sys.argv", ["build_runtime_truth_dashboard_seed.py", "--db-path", str(db_path)])
    exit_code = main()
    assert exit_code == 0
