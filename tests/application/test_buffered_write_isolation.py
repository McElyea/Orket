from __future__ import annotations

from orket.application.services.memory_commit_buffer import InMemoryCommitStore


def test_buffered_write_isolation_reads_do_not_see_uncommitted_writes() -> None:
    store = InMemoryCommitStore()

    snap1 = store.open_buffer("run-1")
    snap2 = store.open_buffer("run-2")
    assert snap1 == 0
    assert snap2 == 0

    store.append_write("run-1", {"id": "r1"})

    # Both runs read only the committed start snapshot.
    assert store.read_snapshot(snap1) == []
    assert store.read_snapshot(snap2) == []

    store.request_commit("run-1", commit_id="c1", commit_payload_fingerprint="fp1")
    new_snapshot = store.apply_commit("run-1")
    assert new_snapshot == 1

    # Future snapshot sees committed data; old snapshots remain unchanged.
    assert store.read_snapshot(0) == []
    assert store.read_snapshot(1) == [{"id": "r1"}]
