from __future__ import annotations

import json
from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from scripts.protocol.run_protocol_replay_compare import main


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


def _write_receipts(path: Path, *, operation_id: str) -> None:
    path.write_text(
        '{{"receipt_seq":1,"receipt_digest":"{}","operation_id":"{}","event_seq_range":[2,2]}}\n'.format("a" * 64, operation_id),
        encoding="utf-8",
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


def test_run_protocol_replay_compare_receipt_overrides_are_compared(tmp_path: Path) -> None:
    run_a = tmp_path / "run-a.log"
    run_b = tmp_path / "run-b.log"
    receipts_a = tmp_path / "run-a.receipts.log"
    receipts_b = tmp_path / "run-b.receipts.log"
    _write_events(run_a, status="incomplete", ok=True)
    _write_events(run_b, status="incomplete", ok=True)
    _write_receipts(receipts_a, operation_id="op-1")
    _write_receipts(receipts_b, operation_id="op-9")

    exit_code = main(
        [
            "--run-a-events",
            str(run_a),
            "--run-b-events",
            str(run_b),
            "--run-a-receipts",
            str(receipts_a),
            "--run-b-receipts",
            str(receipts_b),
            "--strict",
        ]
    )
    assert exit_code == 1
