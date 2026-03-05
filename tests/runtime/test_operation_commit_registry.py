from __future__ import annotations

from pathlib import Path

from orket.runtime.operation_commit_registry import OperationCommitRegistry


def test_operation_commit_registry_accepts_first_commit(tmp_path: Path) -> None:
    registry = OperationCommitRegistry(tmp_path / "registry.json")
    decision = registry.commit(operation_id="op-1", event_seq=10, entry_digest="a" * 64)
    assert decision["accepted"] is True
    assert decision["error_code"] is None
    assert decision["winner_event_seq"] == 10
    assert decision["winner_entry_digest"] == "a" * 64


def test_operation_commit_registry_rejects_duplicate_with_same_digest(tmp_path: Path) -> None:
    registry = OperationCommitRegistry(tmp_path / "registry.json")
    _ = registry.commit(operation_id="op-1", event_seq=10, entry_digest="a" * 64)
    decision = registry.commit(operation_id="op-1", event_seq=11, entry_digest="a" * 64)
    assert decision["accepted"] is False
    assert decision["error_code"] == "E_DUPLICATE_OPERATION"
    assert decision["winner_event_seq"] == 10
    assert decision["idempotent_reuse"] is True


def test_operation_commit_registry_rejects_conflicting_duplicate(tmp_path: Path) -> None:
    registry = OperationCommitRegistry(tmp_path / "registry.json")
    _ = registry.commit(operation_id="op-1", event_seq=10, entry_digest="a" * 64)
    decision = registry.commit(operation_id="op-1", event_seq=9, entry_digest="b" * 64)
    assert decision["accepted"] is False
    assert decision["error_code"] == "E_DUPLICATE_OPERATION"
    assert decision["winner_event_seq"] == 10
    assert decision["winner_entry_digest"] == "a" * 64
    assert decision["idempotent_reuse"] is False


def test_operation_commit_registry_persists_entries(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    first = OperationCommitRegistry(path)
    _ = first.commit(operation_id="op-2", event_seq=2, entry_digest="b" * 64)
    _ = first.commit(operation_id="op-1", event_seq=1, entry_digest="a" * 64)

    second = OperationCommitRegistry(path)
    winner = second.winner("op-1")
    assert winner is not None
    assert winner["event_seq"] == 1
    entries = second.entries()
    assert [row["operation_id"] for row in entries] == ["op-1", "op-2"]
