from __future__ import annotations

import json
from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from scripts.MidTier.run_protocol_replay_compare import main


def _write_events(path: Path, *, status: str, ok: bool) -> None:
    ledger = AppendOnlyRunLedger(path)
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": "sess-1",
            "run_type": "epic",
            "run_name": "Replay",
            "department": "core",
            "build_id": "build-1",
            "status": "running",
        }
    )
    ledger.append_event(
        {
            "kind": "operation_result",
            "session_id": "sess-1",
            "operation_id": "op-1",
            "tool": "write_file",
            "result": {"ok": ok},
        }
    )
    ledger.append_event(
        {
            "kind": "run_finalized",
            "session_id": "sess-1",
            "status": status,
            "failure_class": None if status == "incomplete" else "ExecutionFailed",
            "failure_reason": None if status == "incomplete" else "failed",
        }
    )


def test_run_protocol_replay_compare_writes_output_file(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a.log"
    run_b = tmp_path / "run-b.log"
    out = tmp_path / "compare.json"
    _write_events(run_a, status="incomplete", ok=True)
    _write_events(run_b, status="incomplete", ok=True)

    exit_code = main(
        [
            "--run-a-events",
            str(run_a),
            "--run-b-events",
            str(run_b),
            "--out",
            str(out),
            "--strict",
        ]
    )

    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["deterministic_match"] is True
    assert payload["differences"] == []


def test_run_protocol_replay_compare_strict_exits_non_zero_on_divergence(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a.log"
    run_b = tmp_path / "run-b.log"
    _write_events(run_a, status="incomplete", ok=True)
    _write_events(run_b, status="failed", ok=False)

    exit_code = main(
        [
            "--run-a-events",
            str(run_a),
            "--run-b-events",
            str(run_b),
            "--strict",
        ]
    )
    assert exit_code == 1
