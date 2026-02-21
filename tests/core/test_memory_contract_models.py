from __future__ import annotations

import pytest

from orket.core.contracts import DeterminismTraceContract, RetrievalTraceEventContract


def test_determinism_trace_contract_accepts_valid_payload() -> None:
    payload = {
        "run_id": "run-1",
        "workflow_id": "wf-1",
        "memory_snapshot_id": "snap-1",
        "visibility_mode": "read_only",
        "model_config_id": "model-1",
        "policy_set_id": "policy-1",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [
            {
                "event_id": "evt-0",
                "index": 0,
                "role": "coder",
                "interceptor": "before_prompt",
                "decision_type": "prompt_build",
                "tool_calls": [],
                "guardrails_triggered": [],
                "retrieval_event_ids": [],
            }
        ],
        "output": {
            "output_type": "text",
            "output_shape_hash": "abc",
            "normalization_version": "json-v1",
        },
    }
    contract = DeterminismTraceContract.model_validate(payload)
    assert contract.visibility_mode == "read_only"


def test_determinism_trace_contract_rejects_non_contiguous_event_indexes() -> None:
    payload = {
        "run_id": "run-1",
        "workflow_id": "wf-1",
        "memory_snapshot_id": "snap-1",
        "visibility_mode": "read_only",
        "model_config_id": "model-1",
        "policy_set_id": "policy-1",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [
            {
                "event_id": "evt-0",
                "index": 0,
                "role": "coder",
                "interceptor": "before_prompt",
                "decision_type": "prompt_build",
                "tool_calls": [],
                "guardrails_triggered": [],
                "retrieval_event_ids": [],
            },
            {
                "event_id": "evt-2",
                "index": 2,
                "role": "coder",
                "interceptor": "after_model",
                "decision_type": "emit_output",
                "tool_calls": [],
                "guardrails_triggered": [],
                "retrieval_event_ids": [],
            },
        ],
        "output": {
            "output_type": "text",
            "output_shape_hash": "abc",
            "normalization_version": "json-v1",
        },
    }
    with pytest.raises(ValueError, match="events must be contiguous"):
        DeterminismTraceContract.model_validate(payload)


def test_determinism_trace_contract_enforces_non_live_visibility_for_determinism() -> None:
    payload = {
        "run_id": "run-1",
        "workflow_id": "wf-1",
        "memory_snapshot_id": "snap-1",
        "visibility_mode": "live_read_write",
        "model_config_id": "model-1",
        "policy_set_id": "policy-1",
        "determinism_trace_schema_version": "memory.determinism_trace.v1",
        "events": [],
        "output": {
            "output_type": "text",
            "output_shape_hash": "abc",
            "normalization_version": "json-v1",
        },
    }
    contract = DeterminismTraceContract.model_validate(payload)
    with pytest.raises(ValueError, match="may not use live_read_write"):
        contract.enforce_non_live_visibility()


def test_retrieval_trace_contract_rejects_non_contiguous_ranks() -> None:
    payload = {
        "retrieval_event_id": "ret-1",
        "run_id": "run-1",
        "event_id": "evt-1",
        "policy_id": "policy-1",
        "policy_version": "v1",
        "query_normalization_version": "json-v1",
        "query_fingerprint": "abc",
        "retrieval_mode": "text_to_vector",
        "candidate_count": 2,
        "selected_records": [
            {"record_id": "a", "record_type": "chunk", "score": 0.8, "rank": 1},
            {"record_id": "b", "record_type": "chunk", "score": 0.7, "rank": 3},
        ],
        "applied_filters": {},
        "retrieval_trace_schema_version": "memory.retrieval_trace.v1",
    }
    with pytest.raises(ValueError, match="ranks must be contiguous"):
        RetrievalTraceEventContract.model_validate(payload)
