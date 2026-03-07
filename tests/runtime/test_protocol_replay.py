from __future__ import annotations

import json
from pathlib import Path

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.runtime.protocol_replay import (
    ProtocolReplayEngine,
    artifact_digest_inventory,
    receipt_digest_inventory,
    runtime_contract_hash,
)
from orket.runtime.runtime_policy_versions import runtime_policy_versions_snapshot


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


def _write_receipts(path: Path, *, operation_id: str = "op-1", receipt_seq: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "receipt_seq": receipt_seq,
        "receipt_digest": "a" * 64,
        "operation_id": operation_id,
        "event_seq_range": [2, 2],
        "execution_capsule": {
            "network_mode": "allowlist",
            "network_allowlist_hash": "b" * 64,
            "clock_mode": "artifact_replay",
            "clock_artifact_ref": "artifacts/clock/run-a.json",
            "clock_artifact_hash": "c" * 64,
            "timezone": "UTC",
            "locale": "C.UTF-8",
            "env_allowlist_hash": "d" * 64,
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_artifact_digest_inventory_is_stable_and_sorted(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    (artifact_root / "b").mkdir(parents=True, exist_ok=True)
    (artifact_root / "a").mkdir(parents=True, exist_ok=True)
    (artifact_root / "b" / "z.txt").write_text("z", encoding="utf-8")
    (artifact_root / "a" / "x.txt").write_text("x", encoding="utf-8")

    inventory = artifact_digest_inventory(artifact_root)
    assert [row["path"] for row in inventory] == ["a/x.txt", "b/z.txt"]
    assert all(len(row["sha256"]) == 64 for row in inventory)


def test_receipt_digest_inventory_is_stable_and_sorted(tmp_path: Path) -> None:
    receipts = tmp_path / "receipts.log"
    receipts.write_text(
        "\n".join(
            [
                '{"receipt_seq":2,"receipt_digest":"%s","operation_id":"op-2","event_seq_range":[4,4]}' % ("b" * 64),
                '{"receipt_seq":1,"receipt_digest":"%s","operation_id":"op-1","event_seq_range":[2,2]}' % ("a" * 64),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    inventory = receipt_digest_inventory(receipts)
    assert [row["receipt_seq"] for row in inventory] == [1, 2]
    assert [row["operation_id"] for row in inventory] == ["op-1", "op-2"]
    assert inventory[0]["execution_capsule"] == {}
    assert inventory[1]["execution_capsule"] == {}


def test_receipt_digest_inventory_surfaces_execution_capsule_subset(tmp_path: Path) -> None:
    receipts = tmp_path / "receipts.log"
    _write_receipts(receipts, operation_id="op-clock")
    inventory = receipt_digest_inventory(receipts)
    assert len(inventory) == 1
    capsule = inventory[0]["execution_capsule"]
    assert capsule["network_mode"] == "allowlist"
    assert capsule["clock_mode"] == "artifact_replay"
    assert capsule["clock_artifact_ref"] == "artifacts/clock/run-a.json"
    assert capsule["network_allowlist_hash"] == "b" * 64
    assert capsule["clock_artifact_hash"] == "c" * 64


def test_protocol_replay_engine_reconstructs_summary(tmp_path: Path) -> None:
    events = tmp_path / "runs" / "sess-1" / "events.log"
    _write_run_events(events, status="incomplete", operation_ok=True)
    _write_receipts(events.with_name("receipts.log"))
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
    assert replay["receipt_count"] == 1
    assert len(replay["state_digest"]) == 64
    assert len(replay["artifact_inventory"]) == 1


def test_protocol_replay_engine_compare_reports_match_for_identical_runs(tmp_path: Path) -> None:
    run_a = tmp_path / "run_a" / "events.log"
    run_b = tmp_path / "run_b" / "events.log"
    _write_run_events(run_a, status="incomplete", operation_ok=True)
    _write_run_events(run_b, status="incomplete", operation_ok=True)
    _write_receipts(run_a.with_name("receipts.log"))
    _write_receipts(run_b.with_name("receipts.log"))

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
    _write_receipts(run_a.with_name("receipts.log"), operation_id="op-1", receipt_seq=1)
    _write_receipts(run_b.with_name("receipts.log"), operation_id="op-9", receipt_seq=1)

    engine = ProtocolReplayEngine()
    comparison = engine.compare_replays(run_a_events_path=run_a, run_b_events_path=run_b)

    assert comparison["deterministic_match"] is False
    fields = {row["field"] for row in comparison["differences"]}
    assert "status" in fields
    assert "operations" in fields
    assert "receipt_inventory" in fields
    assert comparison["state_digest_a"] != comparison["state_digest_b"]


# Layer: contract
def test_protocol_replay_engine_includes_runtime_contract_snapshot_versions(tmp_path: Path) -> None:
    events = tmp_path / "runs" / "sess-contracts" / "events.log"
    _write_run_events(events, status="incomplete", operation_ok=True)

    engine = ProtocolReplayEngine()
    replay = engine.replay_from_ledger(events_log_path=events)

    contracts = replay["runtime_contract_snapshots"]
    assert contracts["tool_registry_version"] == "1.2.0"
    assert contracts["artifact_schema_registry_version"] == "1.0"
    assert contracts["compatibility_map_schema_version"] == "1.0"
    assert replay["runtime_policy_versions"] == runtime_policy_versions_snapshot()
    assert replay["ledger_schema_version"] == "1.0"
    assert replay["runtime_contract_hash"] == runtime_contract_hash(contracts, replay["runtime_policy_versions"])


# Layer: contract
def test_runtime_contract_hash_changes_when_runtime_policy_versions_change() -> None:
    base_contracts = {
        "tool_registry_version": "1.2.0",
        "artifact_schema_registry_version": "1.0",
        "compatibility_map_schema_version": "1.0",
        "tool_registry_snapshot_hash": "a" * 64,
        "artifact_schema_snapshot_hash": "b" * 64,
        "tool_contract_snapshot_hash": "c" * 64,
    }
    base_policies = runtime_policy_versions_snapshot()
    changed_policies = dict(base_policies)
    changed_policies["retry_policy"] = "2.0"
    assert runtime_contract_hash(base_contracts, base_policies) != runtime_contract_hash(base_contracts, changed_policies)


# Layer: contract
def test_protocol_replay_engine_rejects_incompatible_ledger_schema_version(tmp_path: Path) -> None:
    events = tmp_path / "runs" / "sess-schema-mismatch" / "events.log"
    ledger = AppendOnlyRunLedger(events)
    ledger.append_event({"kind": "run_started", "session_id": "sess-schema-mismatch", "ledger_schema_version": "1.0"})
    ledger.append_event({"kind": "run_finalized", "session_id": "sess-schema-mismatch", "ledger_schema_version": "2.0"})

    engine = ProtocolReplayEngine()
    try:
        _ = engine.replay_from_ledger(events_log_path=events)
    except ValueError as exc:
        assert "E_REPLAY_LEDGER_SCHEMA_INCOMPATIBLE" in str(exc)
    else:
        raise AssertionError("expected ledger schema incompatibility failure")
