from __future__ import annotations

import pytest

from orket.application.services.memory_commit_buffer import InMemoryCommitStore


def test_memory_commit_recovery_single_owner_lease_and_reassignment() -> None:
    store = InMemoryCommitStore()
    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")

    assert store.try_acquire_recovery_lease("run-1", "worker-a", now_ts=10.0, lease_seconds=5.0) is True
    assert store.try_acquire_recovery_lease("run-1", "worker-b", now_ts=12.0, lease_seconds=5.0) is False
    # After expiry, ownership can be reassigned.
    assert store.try_acquire_recovery_lease("run-1", "worker-b", now_ts=16.0, lease_seconds=5.0) is True


def test_memory_commit_recovery_marks_storage_apply_failed() -> None:
    store = InMemoryCommitStore()
    store.open_buffer("run-1")
    store.append_write("run-1", {"id": "r1"})
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")

    result = store.recover_pending_commit(
        "run-1",
        worker_id="worker-a",
        now_ts=10.0,
        lease_seconds=5.0,
        fail_apply=True,
    )
    assert result is None
    assert store.buffer_state("run-1") == "commit_aborted"
    assert store.buffer_reason_code("run-1") == "storage_apply_failed"


def test_memory_commit_recovery_requires_lease_ownership() -> None:
    store = InMemoryCommitStore()
    store.open_buffer("run-1")
    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    assert store.try_acquire_recovery_lease("run-1", "worker-a", now_ts=1.0, lease_seconds=10.0) is True

    with pytest.raises(ValueError, match="lease_not_acquired"):
        store.recover_pending_commit(
            "run-1",
            worker_id="worker-b",
            now_ts=2.0,
            lease_seconds=5.0,
            fail_apply=False,
        )
