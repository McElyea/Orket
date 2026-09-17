"""Independent registry owners cannot replace a retained first commit."""
import json

import pytest

from orket.adapters.storage.operation_commit_registry import OperationCommitRegistry
from orket.core.contracts.protocol_error_codes import is_registered_protocol_error_code

pytestmark = pytest.mark.integration


# Layer: integration
def test_stale_registry_owner_preserves_first_durable_commit(tmp_path):
    path = tmp_path / "operation_commits.json"
    first, stale = OperationCommitRegistry(path), OperationCommitRegistry(path)
    assert first.entries() == stale.entries() == []
    accepted = first.commit(operation_id="op-1", event_seq=1, entry_digest="a" * 64)
    duplicate = stale.commit(operation_id="op-1", event_seq=2, entry_digest="b" * 64)
    assert accepted["accepted"] and not duplicate["accepted"]
    assert duplicate["winner_entry_digest"] == "a" * 64
    assert OperationCommitRegistry(path).winner("op-1")["entry_digest"] == "a" * 64


# Layer: integration
def test_failed_registry_persistence_does_not_publish_an_in_memory_winner(tmp_path, monkeypatch):
    path = tmp_path / "operation_commits.json"
    registry = OperationCommitRegistry(path)

    def fail(*_, **__):
        raise OSError("controlled-persistence-failure")

    with monkeypatch.context() as patch:
        patch.setattr(registry, "_persist", fail)
        with pytest.raises(OSError, match="controlled-persistence-failure"):
            registry.commit(operation_id="op-1", event_seq=1, entry_digest="a" * 64)
    assert not path.exists()
    assert registry.winner("op-1") is None
    retried = registry.commit(operation_id="op-1", event_seq=1, entry_digest="a" * 64)
    assert retried["accepted"]
    assert OperationCommitRegistry(path).winner("op-1")["entry_digest"] == "a" * 64


@pytest.mark.parametrize("original", [b"{truncated", b'{"entries":null}', b'{"entries":[{"operation_id":"lost"}]}'])
# Layer: integration
def test_corrupt_registry_refuses_new_commit_without_replacing_evidence(tmp_path, original):
    path = tmp_path / "operation_commits.json"
    path.write_bytes(original)
    with pytest.raises((ValueError, RuntimeError)) as refused:
        OperationCommitRegistry(path).commit(operation_id="op-new", event_seq=1, entry_digest="b" * 64)
    assert is_registered_protocol_error_code(str(refused.value))
    assert path.read_bytes() == original


@pytest.mark.parametrize("sequence", [1.5, "1", True, 0, -1])
# Layer: integration
def test_registry_refuses_invalid_stored_sequence_without_normalizing_history(tmp_path, sequence):
    original = json.dumps({"entries": [{"operation_id": "op-1", "event_seq": sequence, "entry_digest": "a" * 64}]}).encode()
    path = tmp_path / "operation_commits.json"
    path.write_bytes(original)
    with pytest.raises(ValueError) as refused:
        OperationCommitRegistry(path).commit(operation_id="op-new", event_seq=2, entry_digest="b" * 64)
    assert is_registered_protocol_error_code(str(refused.value))
    assert path.read_bytes() == original


@pytest.mark.parametrize("sequence", [1.5, "1", True, 0, -1])
# Layer: integration
def test_registry_refuses_invalid_new_sequence_before_creating_authority(tmp_path, sequence):
    path = tmp_path / "operation_commits.json"
    with pytest.raises(ValueError) as refused:
        OperationCommitRegistry(path).commit(operation_id="op-new", event_seq=sequence, entry_digest="b" * 64)
    assert is_registered_protocol_error_code(str(refused.value))
    assert not path.exists()
