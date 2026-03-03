from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.execution import OpenClawJsonlSubprocessAdapter
from orket.kernel.v1.nervous_system_contract import tool_profile_digest
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1, commit_proposal_v1, end_session_v1, projection_pack_v1
from orket.kernel.v1.nervous_system_runtime_extensions import (
    consume_credential_token_v1,
    decide_approval_v1,
    get_session_ledger_events_v1,
    issue_credential_token_v1,
)
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests, utc_iso_now

REQUIRED_EVENT_TYPES = [
    "projection.issued",
    "proposal.received",
    "admission.decided",
    "approval.requested",
    "approval.decided",
    "credential.token_issued",
    "credential.token_used",
    "action.executed",
    "action.result_validated",
    "incident.detected",
    "session.ended",
    "commit.recorded",
]


def _collect_event_digests(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_type = {event_type: [] for event_type in REQUIRED_EVENT_TYPES}
    for event in events:
        event_type = str(event.get("event_type") or "")
        digest = str(event.get("event_digest") or "")
        if event_type in by_type and digest:
            by_type[event_type].append(digest)
    return by_type


def _base_request(*, session_id: str, trace_id: str, request_id: str) -> dict[str, str]:
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
    }


def _projection(session_id: str, trace_id: str, request_id: str, tool_name: str) -> dict[str, Any]:
    return projection_pack_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "purpose": "action_path",
            "tool_context_summary": {"tool": tool_name},
            "policy_context": {"mode": "strict"},
        }
    )


def _finalize_session(session_id: str, trace_id: str, request_id: str) -> dict[str, list[str]]:
    end_session_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "reason": "live-evidence",
        }
    )
    events = get_session_ledger_events_v1(session_id)
    return _collect_event_digests(events)


def _scenario_base(
    *,
    name: str,
    session_id: str,
    trace_id: str,
    request_id: str,
    projection: dict[str, Any],
    admission: dict[str, Any],
    tool_profile_digest_value: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "proposal_digest": admission["proposal_digest"],
        "admission_decision_digest": admission["decision_digest"],
        "approval_id": admission.get("approval_id"),
        "policy_digest": projection["policy_digest"],
        "tool_profile_digest": tool_profile_digest_value,
        "admission_decision": admission["admission_decision"]["decision"],
    }


def _run_blocked_scenario(response: dict[str, Any]) -> dict[str, Any]:
    session_id = "ns-live-blocked"
    trace_id = "trace-blocked-001"
    request_id = "req-blocked-001"
    proposal = dict(response["proposal"])

    projection = _projection(session_id, trace_id, request_id, "fs.delete")
    admission = admit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal": proposal,
        }
    )
    commit = commit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": admission["proposal_digest"],
            "admission_decision_digest": admission["decision_digest"],
            "execution_result_digest": "1" * 64,
        }
    )
    event_digests = _finalize_session(session_id, trace_id, request_id)
    record = _scenario_base(
        name="blocked_destructive",
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        projection=projection,
        admission=admission,
        tool_profile_digest_value=tool_profile_digest(dict(proposal.get("payload", {}).get("tool_profile") or {})),
    )
    record.update(
        {
            "token_id_hash": None,
            "commit_invoked": True,
            "commit_status": commit["status"],
            "required_event_digests": event_digests,
        }
    )
    return record


def _run_approval_scenario(response: dict[str, Any]) -> dict[str, Any]:
    session_id = "ns-live-approval"
    trace_id = "trace-approval-001"
    request_id = "req-approval-001"
    proposal = dict(response["proposal"])

    projection = _projection(session_id, trace_id, request_id, "fs.write_patch")
    admission = admit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal": proposal,
        }
    )
    approval_id = str(admission.get("approval_id") or "")
    approval = decide_approval_v1(
        approval_id=approval_id,
        decision="approve",
        edited_proposal=None,
        notes="live-evidence approval",
    )
    commit = commit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": admission["proposal_digest"],
            "admission_decision_digest": admission["decision_digest"],
            "approval_id": approval_id,
            "execution_result_digest": "2" * 64,
        }
    )
    event_digests = _finalize_session(session_id, trace_id, request_id)
    record = _scenario_base(
        name="approval_required",
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        projection=projection,
        admission=admission,
        tool_profile_digest_value=tool_profile_digest(dict(proposal.get("payload", {}).get("tool_profile") or {})),
    )
    record.update(
        {
            "approval_id": approval_id,
            "token_id_hash": None,
            "approval_status": approval["approval"]["status"],
            "commit_invoked": True,
            "commit_status": commit["status"],
            "required_event_digests": event_digests,
        }
    )
    return record


def _run_credential_scenario(response: dict[str, Any], *, replay: bool) -> dict[str, Any]:
    name = "credentialed_token_replay" if replay else "credentialed_token"
    session_id = "ns-live-credential-replay" if replay else "ns-live-credential"
    trace_id = "trace-credential-replay-001" if replay else "trace-credential-001"
    request_id = "req-credential-replay-001" if replay else "req-credential-001"
    proposal = dict(response["proposal"])
    token_request = dict(response.get("token_request") or {})

    projection = _projection(session_id, trace_id, request_id, "demo.credentialed_echo")
    admission = admit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal": proposal,
        }
    )
    approval_id = str(admission.get("approval_id") or "")
    approval = decide_approval_v1(
        approval_id=approval_id,
        decision="approve",
        edited_proposal=None,
        notes="live-evidence approval",
    )

    issued = issue_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": admission["proposal_digest"],
            "admission_decision_digest": admission["decision_digest"],
            "approval_id": approval_id,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_definition": token_request["tool_profile_definition"],
        }
    )
    first = consume_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "token": issued["token"],
            "proposal_digest": admission["proposal_digest"],
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )

    replay_reason = ""
    if replay:
        second = consume_credential_token_v1(
            {
                **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
                "token": issued["token"],
                "proposal_digest": admission["proposal_digest"],
                "tool_name": token_request["tool_name"],
                "scope_json": token_request["scope_json"],
                "tool_profile_digest": issued["tool_profile_digest"],
            }
        )
        replay_reason = str(second.get("reason_code") or "")
        commit = commit_proposal_v1(
            {
                **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
                "proposal_digest": admission["proposal_digest"],
                "admission_decision_digest": admission["decision_digest"],
                "approval_id": approval_id,
                "execution_result_digest": "4" * 64,
                "execution_error_reason_code": replay_reason,
            }
        )
    else:
        commit = commit_proposal_v1(
            {
                **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
                "proposal_digest": admission["proposal_digest"],
                "admission_decision_digest": admission["decision_digest"],
                "approval_id": approval_id,
                "execution_result_digest": "3" * 64,
            }
        )

    event_digests = _finalize_session(session_id, trace_id, request_id)
    if replay and len(event_digests["credential.token_used"]) != 1:
        raise RuntimeError("token replay scenario emitted unexpected credential.token_used count")

    record = _scenario_base(
        name=name,
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        projection=projection,
        admission=admission,
        tool_profile_digest_value=issued["tool_profile_digest"],
    )
    record.update(
        {
            "approval_id": approval_id,
            "token_id_hash": issued["token_id_hash"],
            "scope_digest": issued["scope_digest"],
            "approval_status": approval["approval"]["status"],
            "token_consume_ok": first["ok"],
            "commit_invoked": True,
            "commit_status": commit["status"],
            "required_event_digests": event_digests,
        }
    )
    if replay:
        record["token_replay_reason_code"] = replay_reason
        record["token_replay_consume_ok"] = False
    return record


async def _run_live() -> dict[str, Any]:
    os.environ["ORKET_ENABLE_NERVOUS_SYSTEM"] = "true"
    os.environ["ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS"] = "true"
    os.environ["ORKET_USE_TOOL_PROFILE_RESOLVER"] = "false"
    reset_runtime_state_for_tests()

    adapter = OpenClawJsonlSubprocessAdapter(
        command=[sys.executable, "tools/fake_openclaw_adapter_strict.py"],
        io_timeout_seconds=15.0,
    )
    requests = [
        {"type": "next_action", "scenario_kind": "blocked_destructive"},
        {"type": "next_action", "scenario_kind": "approval_required"},
        {"type": "next_action", "scenario_kind": "credentialed_token"},
        {"type": "next_action", "scenario_kind": "credentialed_token_replay"},
    ]
    responses = await adapter.run_requests(requests)
    if any(str(item.get("type") or "") != "action_proposal" for item in responses):
        raise RuntimeError("fake OpenClaw adapter returned unexpected message type")

    scenarios = [
        _run_blocked_scenario(responses[0]),
        _run_approval_scenario(responses[1]),
        _run_credential_scenario(responses[2], replay=False),
        _run_credential_scenario(responses[3], replay=True),
    ]

    return {
        "generated_at": utc_iso_now(),
        "policy_flag_mode": "pre_resolved_flags",
        "adapter_run": {
            "mode": "subprocess_jsonl",
            "path": "primary",
            "command": [sys.executable, "tools/fake_openclaw_adapter_strict.py"],
            "request_count": len(requests),
            "response_count": len(responses),
            "status": "ok",
        },
        "required_event_types": REQUIRED_EVENT_TYPES,
        "scenarios": scenarios,
    }


async def main() -> int:
    artifact = await _run_live()
    output_path = Path("benchmarks/results/nervous_system_live_evidence.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact, ensure_ascii=False, indent=2)
    await asyncio.to_thread(output_path.write_text, payload, "utf-8")
    print(str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
