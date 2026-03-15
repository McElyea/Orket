from __future__ import annotations

from orket.runtime.run_summary import build_run_summary_payload, reconstruct_run_summary
from orket.runtime.run_summary_artifact_provenance import ARTIFACT_PROVENANCE_KEY

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"


def _artifact_provenance_payload(*, artifact_provenance_facts: dict) -> dict:
    return build_run_summary_payload(
        run_id="sess-artifact-provenance",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["write_file"],
        artifacts={
            "run_identity": {"run_id": "sess-artifact-provenance", "start_time": _STARTED_AT},
            "artifact_provenance_facts": artifact_provenance_facts,
        },
    )[ARTIFACT_PROVENANCE_KEY]


# Layer: contract
def test_artifact_provenance_contract() -> None:
    artifact_provenance = _artifact_provenance_payload(
        artifact_provenance_facts={
            "artifacts": [
                {
                    "artifact_path": "agent_output/main.py",
                    "artifact_type": "source_code",
                    "generator": "tool.write_file",
                    "generator_version": "1.0.0",
                    "source_hash": "a" * 64,
                    "produced_at": "2036-03-05T12:00:03+00:00",
                    "truth_classification": "direct",
                    "step_id": "COD-1:1",
                    "operation_id": "op-main",
                    "issue_id": "COD-1",
                    "role_name": "coder",
                    "turn_index": 1,
                    "tool_call_hash": "b" * 64,
                    "receipt_digest": "c" * 64,
                }
            ]
        }
    )
    assert artifact_provenance["artifacts"] == [
        {
            "artifact_path": "agent_output/main.py",
            "artifact_type": "source_code",
            "generator": "tool.write_file",
            "generator_version": "1.0.0",
            "source_hash": "a" * 64,
            "produced_at": "2036-03-05T12:00:03+00:00",
            "truth_classification": "direct",
            "step_id": "COD-1:1",
            "operation_id": "op-main",
            "issue_id": "COD-1",
            "role_name": "coder",
            "turn_index": 1,
            "tool_call_hash": "b" * 64,
            "receipt_digest": "c" * 64,
        }
    ]


# Layer: contract
def test_artifact_provenance_extension_is_omitted_without_artifacts() -> None:
    payload = build_run_summary_payload(
        run_id="sess-artifact-provenance-none",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["write_file"],
        artifacts={"run_identity": {"run_id": "sess-artifact-provenance-none", "start_time": _STARTED_AT}},
    )
    assert ARTIFACT_PROVENANCE_KEY not in payload


# Layer: integration
def test_artifact_provenance_reconstruction_matches_emitted_summary() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-artifact-provenance-reconstruct",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": {"run_id": "sess-artifact-provenance-reconstruct", "start_time": _STARTED_AT},
            },
        },
        {
            "kind": "artifact_provenance_fact",
            "event_seq": 2,
            "artifact_provenance_facts": {
                "artifacts": [
                    {
                        "artifact_path": "agent_output/requirements.txt",
                        "artifact_type": "requirements_document",
                        "generator": "tool.write_file",
                        "generator_version": "1.0.0",
                        "source_hash": "d" * 64,
                        "produced_at": "2036-03-05T12:00:02+00:00",
                        "truth_classification": "direct",
                        "step_id": "REQ-1:1",
                        "operation_id": "op-req",
                        "issue_id": "REQ-1",
                        "role_name": "requirements_analyst",
                        "turn_index": 1,
                    }
                ]
            },
        },
        {
            "kind": "tool_call",
            "event_seq": 3,
            "tool_name": "write_file",
        },
        {
            "kind": "run_finalized",
            "event_seq": 4,
            "run_id": "sess-artifact-provenance-reconstruct",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]
    reconstructed = reconstruct_run_summary(events, session_id="sess-artifact-provenance-reconstruct")
    emitted = build_run_summary_payload(
        run_id="sess-artifact-provenance-reconstruct",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["write_file"],
        artifacts={
            "run_identity": {"run_id": "sess-artifact-provenance-reconstruct", "start_time": _STARTED_AT},
            "artifact_provenance_facts": {
                "artifacts": [
                    {
                        "artifact_path": "agent_output/requirements.txt",
                        "artifact_type": "requirements_document",
                        "generator": "tool.write_file",
                        "generator_version": "1.0.0",
                        "source_hash": "d" * 64,
                        "produced_at": "2036-03-05T12:00:02+00:00",
                        "truth_classification": "direct",
                        "step_id": "REQ-1:1",
                        "operation_id": "op-req",
                        "issue_id": "REQ-1",
                        "role_name": "requirements_analyst",
                        "turn_index": 1,
                    }
                ]
            },
        },
    )
    assert reconstructed == emitted
