from __future__ import annotations

from pathlib import Path

from orket.application.services.memory_commit_buffer import JsonFileCommitStore


def test_json_file_commit_store_persists_snapshot_progression(tmp_path: Path) -> None:
    state_file = tmp_path / "memory_commit_state.json"

    store = JsonFileCommitStore(state_file)
    assert store.current_snapshot_id() == 0
    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    snapshot = store.apply_commit("run-1")
    assert snapshot == 1
    assert store.current_snapshot_id() == 1

    reopened = JsonFileCommitStore(state_file)
    assert reopened.current_snapshot_id() == 1
    assert reopened.read_snapshot(1) == [{"id": "r1"}]


def test_json_file_commit_store_idempotency_survives_restart(tmp_path: Path) -> None:
    state_file = tmp_path / "memory_commit_state.json"

    store = JsonFileCommitStore(state_file)
    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    store.apply_commit("run-1")

    reopened = JsonFileCommitStore(state_file)
    reopened.open_buffer("run-2")
    reopened.request_commit("run-2", commit_id="c1", commit_payload_fingerprint="fp1")
    replay = reopened.apply_commit("run-2")
    assert replay is None
    assert reopened.current_snapshot_id() == 1
