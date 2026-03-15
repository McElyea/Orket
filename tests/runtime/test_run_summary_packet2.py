from __future__ import annotations

from orket.runtime.run_summary import build_run_summary_payload, reconstruct_run_summary

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"
_PACKET2_KEY = "truthful_runtime_packet2"


def _packet2_payload(*, packet2_facts: dict) -> dict:
    return build_run_summary_payload(
        run_id="sess-packet2",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={
            "run_identity": {"run_id": "sess-packet2", "start_time": _STARTED_AT},
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
def test_packet2_extension_is_omitted_without_repair_entries() -> None:
    payload = build_run_summary_payload(
        run_id="sess-packet2-none",
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=["workspace.read"],
        artifacts={"run_identity": {"run_id": "sess-packet2-none", "start_time": _STARTED_AT}},
    )
    assert _PACKET2_KEY not in payload


# Layer: integration
def test_packet2_reconstruction_matches_emitted_summary() -> None:
    events = [
        {
            "kind": "run_started",
            "event_seq": 1,
            "run_id": "sess-packet2-reconstruct",
            "timestamp": _STARTED_AT,
            "artifacts": {
                "run_identity": {"run_id": "sess-packet2-reconstruct", "start_time": _STARTED_AT},
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
            "run_identity": {"run_id": "sess-packet2-reconstruct", "start_time": _STARTED_AT},
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
