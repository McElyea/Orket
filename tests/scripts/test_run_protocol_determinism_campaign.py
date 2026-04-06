# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from scripts.protocol.run_protocol_determinism_campaign import main


def _write_run(path: Path, *, status: str, ok: bool, session_id: str = "sess-1") -> None:
    ledger = AppendOnlyRunLedger(path / "events.log")
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": session_id,
            "run_type": "epic",
            "run_name": "Campaign",
            "department": "core",
            "build_id": "build-1",
            "status": "running",
        }
    )
    ledger.append_event(
        {
            "kind": "operation_result",
            "session_id": session_id,
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": ok},
        }
    )
    ledger.append_event(
        {
            "kind": "run_finalized",
            "session_id": session_id,
            "status": status,
            "failure_class": None if status == "incomplete" else "ExecutionFailed",
            "failure_reason": None if status == "incomplete" else "failed",
        }
    )


def test_run_protocol_determinism_campaign_reports_clean_match(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    _write_run(runs_root / "run-b", status="incomplete", ok=True)
    out = tmp_path / "campaign.json"

    exit_code = main(
        [
            "--runs-root",
            str(runs_root),
            "--baseline-run-id",
            "run-a",
            "--out",
            str(out),
            "--strict",
        ]
    )
    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["all_match"] is True
    assert payload["mismatch_count"] == 0
    assert payload["candidate_count"] == 2


def test_run_protocol_determinism_campaign_strict_exits_non_zero_on_mismatch(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    _write_run(runs_root / "run-b", status="failed", ok=False)

    exit_code = main(
        [
            "--runs-root",
            str(runs_root),
            "--baseline-run-id",
            "run-a",
            "--strict",
        ]
    )
    assert exit_code == 1
