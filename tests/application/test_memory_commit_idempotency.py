from __future__ import annotations

import pytest

from orket.application.services.memory_commit_buffer import InMemoryCommitStore


def test_memory_commit_idempotency_same_commit_id_same_payload_is_noop() -> None:
    store = InMemoryCommitStore()

    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    first_snapshot = store.apply_commit("run-1")
    assert first_snapshot == 1
    assert store.current_snapshot_id() == 1

    # Replay same commit id + payload: allowed no-op.
    store.open_buffer("run-1-replay")
    store.request_commit("run-1-replay", commit_id="c1", commit_payload_fingerprint="fp1")
    replay_snapshot = store.apply_commit("run-1-replay")
    assert replay_snapshot is None
    assert store.current_snapshot_id() == 1


def test_memory_commit_idempotency_same_commit_id_different_payload_fails() -> None:
    store = InMemoryCommitStore()

    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    store.apply_commit("run-1")

    store.open_buffer("run-2")
    store.request_commit("run-2", commit_id="c1", commit_payload_fingerprint="fp2")
    with pytest.raises(ValueError, match="payload_mismatch"):
        store.apply_commit("run-2")
    assert store.buffer_state("run-2") == "commit_aborted"
    assert store.buffer_reason_code("run-2") == "payload_mismatch"
