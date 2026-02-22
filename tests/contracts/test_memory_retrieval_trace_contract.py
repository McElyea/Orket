from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_memory_retrieval_trace_schema_contract() -> None:
    path = Path("docs/projects/archive/MemoryPersistence/MEMORY_RETRIEVAL_TRACE_SCHEMA.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "memory.retrieval_trace.v1",
        "retrieval_event_id",
        "run_id",
        "event_id",
        "policy_id",
        "policy_version",
        "query_normalization_version",
        "query_fingerprint",
        "retrieval_mode",
        "candidate_count",
        "selected_records",
        "applied_filters",
        "retrieval_trace_schema_version",
        "record_id",
        "record_type",
        "score",
        "rank",
        "score` descending",
        "record_id` ascending",
        "backend-native deterministic mode",
        "deterministic wrapper re-ranking",
    ]

    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required retrieval trace contract tokens: {missing}"


def test_memory_buffer_state_machine_has_single_owner_lease_rule() -> None:
    path = Path("docs/projects/archive/MemoryPersistence/MEMORY_BUFFER_STATE_MACHINE.md")
    assert path.exists(), f"Missing schema doc: {path}"
    text = _read(path)

    required_tokens = [
        "memory.buffer_state_machine.v1",
        "commit_pending",
        "commit_applied",
        "commit_aborted",
        "commit_payload_fingerprint",
        "A `commit_id` may be owned by exactly one recovery worker at a time.",
        "lease-based with explicit timeout and renewal",
        "Expired leases become eligible for reassignment.",
        "Lease timeout default (v1): 30 seconds.",
        "every 10 seconds",
    ]
    missing = [token for token in required_tokens if token not in text]
    assert not missing, f"Missing required buffer recovery contract tokens: {missing}"
