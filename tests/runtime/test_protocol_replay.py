from __future__ import annotations

from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.runtime.protocol_replay import ProtocolReplayEngine, artifact_digest_inventory


def _write_run_events(path: Path, *, status: str, operation_ok: bool) -> None:
    ledger = AppendOnlyRunLedger(path)
    ledger.append_event(
        {
            "kind": "run_started",
            "session_id": "sess-1",
            "run_type": "epic",
            "run_name": "Protocol Replay",
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
            "result": {"ok": operation_ok},
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


def test_artifact_digest_inventory_is_stable_and_sorted(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "b").mkdir(parents=True, exist_ok=True)
    (artifact_root / "a").mkdir(parents=True, exist_ok=True)
    (artifact_root / "b" / "z.txt").write_text("z", encoding="utf-8")
    (artifact_root / "a" / "x.txt").write_text("x", encoding="utf-8")

    inventory = artifact_digest_inventory(artifact_root)
    assert [row["path"] for row in inventory] == ["a/x.txt", "b/z.txt"]
    assert all(len(row["sha256"]) == 64 for row in inventory)


def test_protocol_replay_engine_reconstructs_summary(tmp_path: Path) -> None:
    events = tmp_path / "runs" / "sess-1" / "events.log"
    _write_run_events(events, status="incomplete", operation_ok=True)
    artifacts = tmp_path / "runs" / "sess-1" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "out.txt").write_text("ok", encoding="utf-8")

    engine = ProtocolReplayEngine()
    replay = engine.replay_from_ledger(events_log_path=events, artifact_root=artifacts)

    assert replay["session_id"] == "sess-1"
    assert replay["status"] == "incomplete"
    assert replay["operation_count"] == 1
    assert replay["operations"]["op-1"]["tool"] == "write_file"
    assert replay["operations"]["op-1"]["ok"] is True
    assert replay["event_count"] == 3
    assert replay["last_event_seq"] == 3
    assert len(replay["state_digest"]) == 64
    assert len(replay["artifact_inventory"]) == 1


def test_protocol_replay_engine_compare_reports_match_for_identical_runs(tmp_path: Path) -> None:
    run_a = tmp_path / "run_a" / "events.log"
    run_b = tmp_path / "run_b" / "events.log"
    _write_run_events(run_a, status="incomplete", operation_ok=True)
    _write_run_events(run_b, status="incomplete", operation_ok=True)

    engine = ProtocolReplayEngine()
    comparison = engine.compare_replays(run_a_events_path=run_a, run_b_events_path=run_b)

    assert comparison["deterministic_match"] is True
    assert comparison["differences"] == []
    assert comparison["state_digest_a"] == comparison["state_digest_b"]


def test_protocol_replay_engine_compare_reports_divergence(tmp_path: Path) -> None:
    run_a = tmp_path / "run_a" / "events.log"
    run_b = tmp_path / "run_b" / "events.log"
    _write_run_events(run_a, status="incomplete", operation_ok=True)
    _write_run_events(run_b, status="failed", operation_ok=False)

    engine = ProtocolReplayEngine()
    comparison = engine.compare_replays(run_a_events_path=run_a, run_b_events_path=run_b)

    assert comparison["deterministic_match"] is False
    fields = {row["field"] for row in comparison["differences"]}
    assert "status" in fields
    assert "operations" in fields
    assert comparison["state_digest_a"] != comparison["state_digest_b"]
