from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.runtime.protocol_determinism_campaign import compare_protocol_determinism_campaign


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


def test_compare_protocol_determinism_campaign_returns_clean_match(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    _write_run(runs_root / "run-b", status="incomplete", ok=True)
    payload = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=[],
        baseline_run_id="run-a",
    )
    assert payload["all_match"] is True
    assert payload["mismatch_count"] == 0
    assert payload["candidate_count"] == 2


def test_compare_protocol_determinism_campaign_detects_mismatch(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    _write_run(runs_root / "run-b", status="failed", ok=False)
    payload = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=[],
        baseline_run_id="run-a",
    )
    assert payload["all_match"] is False
    assert payload["mismatch_count"] == 1
    assert any(row["run_id"] == "run-b" and row["deterministic_match"] is False for row in payload["comparisons"])


def test_compare_protocol_determinism_campaign_supports_explicit_run_id_filter(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    _write_run(runs_root / "run-b", status="incomplete", ok=True)
    _write_run(runs_root / "run-c", status="failed", ok=False)
    payload = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=["run-a", "run-b"],
        baseline_run_id="run-a",
    )
    assert payload["candidate_count"] == 2
    assert payload["all_match"] is True
    assert sorted(row["run_id"] for row in payload["comparisons"]) == ["run-a", "run-b"]


def test_compare_protocol_determinism_campaign_marks_missing_events_candidates(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    (runs_root / "run-missing").mkdir(parents=True, exist_ok=True)
    payload = compare_protocol_determinism_campaign(
        runs_root=runs_root,
        run_ids=["run-a", "run-missing"],
        baseline_run_id="run-a",
    )
    assert payload["all_match"] is False
    assert payload["mismatch_count"] == 1
    missing = next(row for row in payload["comparisons"] if row["run_id"] == "run-missing")
    assert missing["status"] == "missing_events"


def test_compare_protocol_determinism_campaign_raises_when_no_runs_found(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    try:
        compare_protocol_determinism_campaign(
            runs_root=runs_root,
            run_ids=[],
            baseline_run_id=None,
        )
    except ValueError as exc:
        assert "No run ids found" in str(exc)
    else:
        raise AssertionError("expected ValueError for empty runs directory")


def test_compare_protocol_determinism_campaign_rejects_traversal_run_id(tmp_path: Path) -> None:
    runs_root = tmp_path / "runs"
    _write_run(runs_root / "run-a", status="incomplete", ok=True)
    try:
        compare_protocol_determinism_campaign(
            runs_root=runs_root,
            run_ids=["run-a", "../outside"],
            baseline_run_id="run-a",
        )
    except ValueError as exc:
        assert "invalid run id" in str(exc)
    else:
        raise AssertionError("expected ValueError for traversal run id")
