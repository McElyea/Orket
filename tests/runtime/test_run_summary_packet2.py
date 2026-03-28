from __future__ import annotations

from orket.runtime.run_summary import build_run_summary_payload, reconstruct_run_summary

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"
_PACKET2_KEY = "truthful_runtime_packet2"


def _run_identity(*, run_id: str) -> dict[str, str | bool]:
    return {
        "run_id": run_id,
        "workload": "packet2-summary",
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
        "projection_only": True,
    }


def _control_plane_refs(*, session_id: str, role_name: str) -> dict[str, str]:
    return {
        "control_plane_run_id": f"turn-tool-run:{session_id}:ISSUE-1:{role_name}:0001",
        "control_plane_attempt_id": f"turn-tool-run:{session_id}:ISSUE-1:{role_name}:0001:attempt:0001",
        "control_plane_step_id": "op-source-receipt",
    }
def _packet2_payload(*, packet2_facts: dict) -> dict:
    return build_run_summary_payload(
        run_id="sess-packet2",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet2"),
            "packet2_facts": packet2_facts,
        },
    )[_PACKET2_KEY]


# Layer: contract
def test_packet2_repair_ledger_contract() -> None:
    packet2 = _packet2_payload(
        packet2_facts={
            "repair_entries": [
                {
                    "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
                    "issue_id": "ISSUE-1",
                    "turn_index": 1,
                    "source_event": "turn_corrective_reprompt",
                    "strategy": "corrective_reprompt",
                    "reasons": [
                        "consistency_scope_contract_not_met",
                        "consistency_scope_contract_not_met",
                        "output_contract_not_met",
                    ],
                    "material_change": True,
                }
            ],
            "final_disposition": "accepted_with_repair",
        }
    )
    assert packet2["repair_ledger"]["repair_occurred"] is True
    assert packet2["repair_ledger"]["repair_count"] == 1
    assert packet2["repair_ledger"]["final_disposition"] == "accepted_with_repair"
    assert packet2["repair_ledger"]["entries"] == [
        {
            "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
            "issue_id": "ISSUE-1",
            "turn_index": 1,
            "source_event": "turn_corrective_reprompt",
            "strategy": "corrective_reprompt",
            "reasons": [
                "consistency_scope_contract_not_met",
                "output_contract_not_met",
            ],
            "material_change": True,
        }
    ]


# Layer: contract
def test_packet2_phase_c_contract_allows_non_repair_sections() -> None:
    packet2 = _packet2_payload(
        packet2_facts={
            "narration_to_effect_audit": {
                "entries": [
                    {
                        "operation_id": "op-source-receipt",
                        "tool": "write_file",
                        "effect_target": "agent_output/source_attribution_receipt.json",
                        "audit_status": "missing",
                        "failure_reason": "workspace_artifact_missing",
                        "issue_id": "EVD-1",
                        "role_name": "evidence_reviewer",
                        "turn_index": 1,
                        **_control_plane_refs(
                            session_id="sess-packet2-audit",
                            role_name="evidence_reviewer",
                        ),
                    }
                ]
            },
            "idempotency": {
                "surfaces": [
                    {
                        "surface": "source_attribution_receipt",
                        "operation_id": "op-source-receipt",
                        "tool": "write_file",
                        "target": "agent_output/source_attribution_receipt.json",
                        "dedupe_status": "single_delivery",
                        "conflict_action": "reuse",
                        "replay_allowed": True,
                        **_control_plane_refs(
                            session_id="sess-packet2-audit",
                            role_name="evidence_reviewer",
                        ),
                    }
                ]
            },
            "source_attribution": {
                "mode": "required",
                "high_stakes": True,
                "synthesis_status": "blocked",
                "artifact_provenance_verified": False,
                "receipt_artifact_path": "agent_output/source_attribution_receipt.json",
                "missing_requirements": ["source_attribution_receipt_missing"],
            },
        }
    )
    assert (packet2["projection_source"], packet2["projection_only"]) == ("packet2_facts", True)
    assert "repair_ledger" not in packet2
    assert packet2["narration_to_effect_audit"]["missing_effect_count"] == 1
    assert packet2["idempotency"]["observed_surface_count"] == 1
    audit_entry = packet2["narration_to_effect_audit"]["entries"][0]
    assert audit_entry["control_plane_run_id"] == (
        "turn-tool-run:sess-packet2-audit:ISSUE-1:evidence_reviewer:0001"
    )
    assert audit_entry["control_plane_attempt_id"] == (
        "turn-tool-run:sess-packet2-audit:ISSUE-1:evidence_reviewer:0001:attempt:0001"
    )
    assert audit_entry["control_plane_step_id"] == "op-source-receipt"
    idempotency_surface = packet2["idempotency"]["surfaces"][0]
    assert idempotency_surface["control_plane_run_id"] == (
        "turn-tool-run:sess-packet2-audit:ISSUE-1:evidence_reviewer:0001"
    )
    assert idempotency_surface["control_plane_attempt_id"] == (
        "turn-tool-run:sess-packet2-audit:ISSUE-1:evidence_reviewer:0001:attempt:0001"
    )
    assert idempotency_surface["control_plane_step_id"] == "op-source-receipt"
    assert packet2["source_attribution"]["synthesis_status"] == "blocked"
    assert packet2["source_attribution"]["missing_requirements"] == ["source_attribution_receipt_missing"]


# Layer: contract
def test_packet2_source_attribution_preserves_control_plane_refs() -> None:
    packet2 = _packet2_payload(
        packet2_facts={
            "source_attribution": {
                "mode": "required",
                "high_stakes": True,
                "synthesis_status": "verified",
                "artifact_provenance_verified": True,
                "receipt_artifact_path": "agent_output/source_attribution_receipt.json",
                "receipt_operation_id": "op-source-receipt",
                **_control_plane_refs(
                    session_id="sess-packet2-source",
                    role_name="lead_architect",
                ),
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "claim": "The implementation is supported by workspace artifacts.",
                        "source_ids": ["design", "implementation", "requirements"],
                    }
                ],
                "sources": [
                    {
                        "source_id": "design",
                        "title": "Design",
                        "uri": "agent_output/design.txt",
                        "kind": "workspace_artifact",
                    },
                    {
                        "source_id": "implementation",
                        "title": "Implementation",
                        "uri": "agent_output/main.py",
                        "kind": "workspace_artifact",
                    },
                    {
                        "source_id": "requirements",
                        "title": "Requirements",
                        "uri": "agent_output/requirements.txt",
                        "kind": "workspace_artifact",
                    },
                ],
                "missing_requirements": [],
            }
        }
    )
    assert packet2["source_attribution"]["receipt_operation_id"] == "op-source-receipt"
    assert packet2["source_attribution"]["control_plane_run_id"] == (
        "turn-tool-run:sess-packet2-source:ISSUE-1:lead_architect:0001"
    )
    assert packet2["source_attribution"]["control_plane_attempt_id"] == (
        "turn-tool-run:sess-packet2-source:ISSUE-1:lead_architect:0001:attempt:0001"
    )
    assert packet2["source_attribution"]["control_plane_step_id"] == "op-source-receipt"

# Layer: contract
def test_packet2_extension_is_omitted_without_repair_entries() -> None:
    payload = build_run_summary_payload(
        run_id="sess-packet2-none",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={"run_identity": _run_identity(run_id="sess-packet2-none")},
    )
    assert _PACKET2_KEY not in payload


# Layer: integration
def test_packet2_reconstruction_matches_emitted_summary_for_phase_c_sections() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-packet2-phase-c",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": _run_identity(run_id="sess-packet2-phase-c"),
            },
        },
        {
            "kind": "packet2_fact",
            "event_seq": 2,
            "packet2_facts": {
                "narration_to_effect_audit": {
                    "entries": [
                        {
                            "operation_id": "op-main",
                            "tool": "write_file",
                            "effect_target": "agent_output/main.py",
                            "audit_status": "verified",
                            "failure_reason": "none",
                            **_control_plane_refs(
                                session_id="sess-packet2-phase-c",
                                role_name="evidence_reviewer",
                            ),
                        }
                    ]
                },
                "idempotency": {
                    "surfaces": [
                        {
                            "surface": "artifact_write",
                            "operation_id": "op-main",
                            "tool": "write_file",
                            "target": "agent_output/main.py",
                            "dedupe_status": "single_delivery",
                            "conflict_action": "reuse",
                            "replay_allowed": True,
                            **_control_plane_refs(
                                session_id="sess-packet2-phase-c",
                                role_name="evidence_reviewer",
                            ),
                        }
                    ]
                },
                "source_attribution": {
                    "mode": "required",
                    "high_stakes": True,
                    "synthesis_status": "verified",
                    "artifact_provenance_verified": True,
                    "receipt_artifact_path": "agent_output/source_attribution_receipt.json",
                    "receipt_operation_id": "op-source-receipt",
                    **_control_plane_refs(
                        session_id="sess-packet2-phase-c",
                        role_name="evidence_reviewer",
                    ),
                    "claims": [
                        {
                            "claim_id": "claim-1",
                            "claim": "The implementation is supported by workspace artifacts.",
                            "source_ids": ["design", "implementation", "requirements"],
                        }
                    ],
                    "sources": [
                        {
                            "source_id": "design",
                            "title": "Design",
                            "uri": "agent_output/design.txt",
                            "kind": "workspace_artifact",
                        },
                        {
                            "source_id": "implementation",
                            "title": "Implementation",
                            "uri": "agent_output/main.py",
                            "kind": "workspace_artifact",
                        },
                        {
                            "source_id": "requirements",
                            "title": "Requirements",
                            "uri": "agent_output/requirements.txt",
                            "kind": "workspace_artifact",
                        },
                    ],
                    "missing_requirements": [],
                },
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
            "run_id": "sess-packet2-phase-c",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]
    reconstructed = reconstruct_run_summary(events, session_id="sess-packet2-phase-c")
    emitted = build_run_summary_payload(
        run_id="sess-packet2-phase-c",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["write_file"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet2-phase-c"),
            "packet2_facts": events[1]["packet2_facts"],
        },
    )
    assert reconstructed == emitted

# Layer: integration
def test_packet2_reconstruction_matches_emitted_summary() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-packet2-reconstruct",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": _run_identity(run_id="sess-packet2-reconstruct"),
            },
        },
        {
            "kind": "packet2_fact",
            "event_seq": 2,
            "packet2_facts": {
                "repair_entries": [
                    {
                        "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
                        "issue_id": "ISSUE-1",
                        "turn_index": 1,
                        "source_event": "turn_corrective_reprompt",
                        "strategy": "corrective_reprompt",
                        "reasons": ["consistency_scope_contract_not_met"],
                        "material_change": True,
                    }
                ],
                "final_disposition": "accepted_with_repair",
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
            "run_id": "sess-packet2-reconstruct",
            "status": "done",
            "timestamp": _FINALIZED_AT,
        },
    ]
    reconstructed = reconstruct_run_summary(events, session_id="sess-packet2-reconstruct")
    emitted = build_run_summary_payload(
        run_id="sess-packet2-reconstruct",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": _run_identity(run_id="sess-packet2-reconstruct"),
            "packet2_facts": {
                "repair_entries": [
                    {
                        "repair_id": "repair:ISSUE-1:1:corrective_reprompt",
                        "issue_id": "ISSUE-1",
                        "turn_index": 1,
                        "source_event": "turn_corrective_reprompt",
                        "strategy": "corrective_reprompt",
                        "reasons": ["consistency_scope_contract_not_met"],
                        "material_change": True,
                    }
                ],
                "final_disposition": "accepted_with_repair",
            },
        },
    )
    assert reconstructed == emitted
