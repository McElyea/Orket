from __future__ import annotations

import pytest

from orket.runtime.run_summary import (
    PACKET1_MISSING_TOKEN,
    build_run_summary_payload,
    reconstruct_run_summary,
)

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"
_PACKET1_KEY = "truthful_runtime_packet1"


def _run_identity(*, run_id: str) -> dict[str, str | bool]:
    return {
        "run_id": run_id,
        "workload": "packet1-summary",
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
        "projection_only": True,
    }


def _packet1_payload(*, packet1_facts: dict) -> dict:
    return build_run_summary_payload(
        run_id="sess-packet1",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet1"),
            "packet1_facts": packet1_facts,
        },
    )[_PACKET1_KEY]


# Layer: contract
@pytest.mark.parametrize(
    ("packet1_facts", "expected_rule", "expected_evidence_source"),
    [
        (
            {
                "primary_artifact_output": {"id": "agent_output/direct.txt", "kind": "artifact"},
            },
            "direct",
            "direct_execution",
        ),
        (
            {
                "primary_artifact_output": {"id": "agent_output/inferred.txt", "kind": "artifact"},
                "inferred_output": True,
            },
            "inferred",
            "runtime_evidence",
        ),
        (
            {
                "primary_artifact_output": {"id": "agent_output/estimated.txt", "kind": "artifact"},
                "estimated_output": True,
            },
            "estimated",
            "estimation_marker",
        ),
        (
            {
                "primary_artifact_output": {"id": "agent_output/repaired.txt", "kind": "artifact"},
                "repair_occurred": True,
                "repair_material_change": True,
            },
            "repaired",
            "validator_repair",
        ),
        (
            {
                "primary_artifact_output": {"id": "agent_output/degraded.txt", "kind": "artifact"},
                "fallback_occurred": True,
            },
            "degraded",
            "fallback_or_reduced_capability",
        ),
    ],
)
def test_packet1_classification_contract(
    packet1_facts: dict,
    expected_rule: str,
    expected_evidence_source: str,
) -> None:
    packet1 = _packet1_payload(packet1_facts=packet1_facts)
    assert packet1["classification"]["classification_applicable"] is True
    assert packet1["classification"]["truth_classification"] == expected_rule
    assert packet1["classification"]["classification_basis"]["rule"] == expected_rule
    assert packet1["classification"]["classification_basis"]["evidence_source"] == expected_evidence_source


# Layer: contract
def test_packet1_primary_output_prefers_work_artifact_before_runtime_verification() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_work_artifact_output": {"id": "agent_output/main.py", "kind": "artifact"},
            "primary_artifact_output": {"id": "agent_output/verification/runtime_verification.json", "kind": "artifact"},
        }
    )
    assert packet1["provenance"]["primary_output_kind"] == "artifact"
    assert packet1["provenance"]["primary_output_id"] == "agent_output/main.py"


# Layer: contract
def test_packet1_provenance_preserves_control_plane_refs_from_primary_output() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_work_artifact_output": {
                "id": "agent_output/main.py",
                "kind": "artifact",
                "control_plane_run_id": "turn-tool-run:sess-packet1:ISSUE-1:lead_architect:0001",
                "control_plane_attempt_id": (
                    "turn-tool-run:sess-packet1:ISSUE-1:lead_architect:0001:attempt:0001"
                ),
                "control_plane_step_id": "op-main",
            }
        }
    )
    assert packet1["projection_source"] == "packet1_facts"
    assert packet1["projection_only"] is True
    assert packet1["provenance"]["control_plane_run_id"] == (
        "turn-tool-run:sess-packet1:ISSUE-1:lead_architect:0001"
    )
    assert packet1["provenance"]["control_plane_attempt_id"] == (
        "turn-tool-run:sess-packet1:ISSUE-1:lead_architect:0001:attempt:0001"
    )
    assert packet1["provenance"]["control_plane_step_id"] == "op-main"


# Layer: contract
def test_packet1_primary_output_prefers_explicit_completion_before_work_artifact() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "explicit_completion_output": {"id": "protocol.reply", "kind": "response"},
            "primary_work_artifact_output": {"id": "agent_output/main.py", "kind": "artifact"},
        }
    )
    assert packet1["provenance"]["primary_output_kind"] == "response"
    assert packet1["provenance"]["primary_output_id"] == "protocol.reply"


# Layer: contract
def test_packet1_missing_token_replaces_placeholder_provenance_values() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_work_artifact_output": {"id": "agent_output/main.py", "kind": "artifact"},
            "intended_model": "unknown",
            "intended_profile": "None",
            "actual_model": "unknown",
            "actual_profile": "None",
        }
    )
    assert packet1["provenance"]["intended_model"] == PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["intended_profile"] == PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["actual_model"] == PACKET1_MISSING_TOKEN
    assert packet1["provenance"]["actual_profile"] == PACKET1_MISSING_TOKEN


# Layer: contract
def test_packet1_no_primary_output_omits_classification() -> None:
    packet1 = _packet1_payload(packet1_facts={})
    assert packet1["provenance"]["primary_output_kind"] == "none"
    assert packet1["classification"] == {"classification_applicable": False}
    assert packet1["defects"]["defects_present"] is False


# Layer: contract
def test_packet1_runtime_verification_path_does_not_become_primary_output_implicitly() -> None:
    payload = build_run_summary_payload(
        run_id="sess-packet1-support-artifact",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=[],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet1-support-artifact"),
            "runtime_verification_path": "agent_output/verification/runtime_verification.json",
        },
    )
    packet1 = payload[_PACKET1_KEY]

    assert packet1["provenance"]["primary_output_kind"] == "none"
    assert packet1["classification"] == {"classification_applicable": False}


# Layer: contract
def test_packet1_defect_taxonomy_contract() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_artifact_output": {"id": "agent_output/runtime_verification.json", "kind": "artifact"},
            "path_mismatch": True,
            "machine_mismatch_indicator": False,
            "repair_occurred": True,
            "fallback_occurred": True,
            "output_presented_as_normal_success": True,
            "run_surface_facts": {"inferred_output": True},
        }
    )
    assert packet1["defects"]["defect_families"] == [
        "classification_divergence",
        "silent_path_mismatch",
        "silent_repaired_success",
        "silent_degraded_success",
    ]
    assert packet1["packet1_conformance"]["status"] == "non_conformant"
    assert packet1["packet1_conformance"]["reasons"] == packet1["defects"]["defect_families"]


# Layer: contract
def test_packet1_silent_unrecorded_fallback_contract() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_artifact_output": {"id": "agent_output/runtime_verification.json", "kind": "artifact"},
            "fallback_path_detected": True,
            "fallback_occurred": False,
        }
    )
    assert packet1["defects"]["defect_families"] == ["silent_unrecorded_fallback"]


# Layer: contract
def test_packet1_negative_detector_case_has_no_defect() -> None:
    packet1 = _packet1_payload(
        packet1_facts={
            "primary_artifact_output": {"id": "agent_output/runtime_verification.json", "kind": "artifact"},
            "machine_mismatch_indicator": True,
            "output_presented_as_normal_success": False,
        }
    )
    assert packet1["defects"] == {"defects_present": False, "defect_families": []}
    assert packet1["packet1_conformance"] == {"status": "conformant", "reasons": []}


# Layer: integration
def test_packet1_reconstruction_matches_emitted_summary() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-packet1-reconstruct",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": _run_identity(run_id="sess-packet1-reconstruct"),
            },
        },
        {
            "kind": "packet1_fact",
            "event_seq": 2,
            "packet1_facts": {
                "primary_artifact_output": {
                    "id": "agent_output/runtime_verification.json",
                    "kind": "artifact",
                    "control_plane_run_id": "turn-tool-run:sess-packet1-reconstruct:ISSUE-1:lead_architect:0001",
                    "control_plane_attempt_id": (
                        "turn-tool-run:sess-packet1-reconstruct:ISSUE-1:lead_architect:0001:attempt:0001"
                    ),
                    "control_plane_step_id": "op-main",
                },
                "inferred_output": True,
            },
        },
        {
            "kind": "tool_call",
            "event_seq": 3,
            "tool_name": "workspace.read",
        },
        {
            "kind": "run_finalized",
            "event_seq": 4,
            "run_id": "sess-packet1-reconstruct",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]
    reconstructed = reconstruct_run_summary(events, session_id="sess-packet1-reconstruct")
    emitted = build_run_summary_payload(
        run_id="sess-packet1-reconstruct",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet1-reconstruct"),
            "packet1_facts": {
                "primary_artifact_output": {
                    "id": "agent_output/runtime_verification.json",
                    "kind": "artifact",
                    "control_plane_run_id": "turn-tool-run:sess-packet1-reconstruct:ISSUE-1:lead_architect:0001",
                    "control_plane_attempt_id": (
                        "turn-tool-run:sess-packet1-reconstruct:ISSUE-1:lead_architect:0001:attempt:0001"
                    ),
                    "control_plane_step_id": "op-main",
                },
                "inferred_output": True,
            },
        },
    )
    assert reconstructed == emitted
