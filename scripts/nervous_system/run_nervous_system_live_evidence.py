from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.execution import OpenClawJsonlSubprocessAdapter  # noqa: E402
from orket.kernel.v1 import api as kernel_api  # noqa: E402
from orket.kernel.v1.nervous_system_contract import tool_profile_digest  # noqa: E402
from orket.kernel.v1.nervous_system_resolver import KNOWN_TOOL_PROFILES  # noqa: E402
from orket.kernel.v1.nervous_system_runtime import (  # noqa: E402
    admit_proposal_v1,
    commit_proposal_v1,
    end_session_v1,
    projection_pack_v1,
)
from orket.kernel.v1.nervous_system_runtime_extensions import (  # noqa: E402
    consume_credential_token_v1,
    decide_approval_v1,
    get_session_ledger_events_v1,
    issue_credential_token_v1,
    list_approvals_v1,
)
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests, utc_iso_now  # noqa: E402
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger  # noqa: E402

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
OUTPUT_PATH = Path("benchmarks/results/nervous_system/nervous_system_live_evidence.json")


def _collect_event_digests(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_type = {event_type: [] for event_type in REQUIRED_EVENT_TYPES}
    for event in events:
        event_type = str(event.get("event_type") or "")
        digest = str(event.get("event_digest") or "")
        if event_type in by_type and digest:
            by_type[event_type].append(digest)
    return by_type


def _base_request(*, session_id: str, trace_id: str, request_id: str) -> dict[str, str]:
    return {"contract_version": "kernel_api/v1", "session_id": session_id, "trace_id": trace_id, "request_id": request_id}


def _projection(session_id: str, trace_id: str, request_id: str, tool_name: str) -> dict[str, Any]:
    return projection_pack_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "purpose": "action_path",
            "tool_context_summary": {"tool": tool_name},
            "policy_context": {"mode": "strict"},
        }
    )


def _proposal_tool_profile_digest(payload: dict[str, Any]) -> str:
    tool_name = str(payload.get("tool_name") or "").strip()
    profile = payload.get("tool_profile")
    if not isinstance(profile, dict):
        profile = KNOWN_TOOL_PROFILES.get(tool_name) or {}
    return tool_profile_digest(dict(profile))


def _finalize_session(session_id: str, trace_id: str, request_id: str) -> dict[str, list[str]]:
    end_session_v1({**_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id), "reason": "live-evidence"})
    return _collect_event_digests(get_session_ledger_events_v1(session_id))


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


def _operator_surface_snapshot(*, session_id: str, trace_id: str, approval_id: str) -> dict[str, Any]:
    approval_items = list_approvals_v1(status=None, session_id=session_id, request_id=None, limit=20)
    approvals_payload = {"items": approval_items, "count": len(approval_items)}
    ledger_payload = kernel_api.list_ledger_events(
        {"contract_version": "kernel_api/v1", "session_id": session_id, "trace_id": trace_id, "limit": 200}
    )
    rebuild_payload = kernel_api.rebuild_pending_approvals(
        {"contract_version": "kernel_api/v1", "session_id": session_id}
    )
    replay_payload = kernel_api.replay_action_lifecycle(
        {"contract_version": "kernel_api/v1", "session_id": session_id, "trace_id": trace_id}
    )
    audit_payload = kernel_api.audit_action_lifecycle(
        {"contract_version": "kernel_api/v1", "session_id": session_id, "trace_id": trace_id}
    )
    approval_rows = [
        row
        for row in list(approvals_payload.get("items") or [])
        if isinstance(row, dict) and str(row.get("approval_id") or "") == approval_id
    ]
    rebuild_ids = {
        str(row.get("approval_id") or "")
        for row in list(rebuild_payload.get("items") or [])
        if isinstance(row, dict)
    }
    return {
        "path": "primary",
        "approvals": {
            "count": int(approvals_payload.get("count") or 0),
            "approval_present": bool(approval_rows),
            "approval_statuses": sorted({str(row.get("status") or "") for row in approval_rows}),
        },
        "ledger_events": {
            "count": int(ledger_payload.get("count") or 0),
            "event_types": sorted(
                {
                    str(row.get("event_type") or "")
                    for row in list(ledger_payload.get("items") or [])
                    if isinstance(row, dict)
                }
            ),
        },
        "rebuild_pending_approvals": {
            "count": int(rebuild_payload.get("count") or 0),
            "approval_present": approval_id in rebuild_ids,
        },
        "replay_action_lifecycle": {
            "event_count": int(replay_payload.get("event_count") or 0),
            "admission_decision": str((replay_payload.get("decision_summary") or {}).get("admission_decision") or ""),
            "approval_status": str((replay_payload.get("decision_summary") or {}).get("approval_status") or ""),
            "commit_status": str((replay_payload.get("decision_summary") or {}).get("commit_status") or ""),
        },
        "audit_action_lifecycle": {
            "ok": bool(audit_payload.get("ok")),
            "checks": {
                str(row.get("check") or ""): bool(row.get("ok"))
                for row in list(audit_payload.get("checks") or [])
                if isinstance(row, dict)
            },
        },
    }


def _run_blocked_scenario(response: dict[str, Any]) -> dict[str, Any]:
    session_id = "ns-live-blocked"
    trace_id = "trace-blocked-001"
    request_id = "req-blocked-001"
    proposal = dict(response["proposal"])
    payload = dict(proposal.get("payload") or {})
    projection = _projection(session_id, trace_id, request_id, "fs.delete")
    admission = admit_proposal_v1({**_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id), "proposal": proposal})
    commit = commit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": admission["proposal_digest"],
            "admission_decision_digest": admission["decision_digest"],
            "execution_result_digest": "1" * 64,
        }
    )
    record = _scenario_base(
        name="blocked_destructive",
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        projection=projection,
        admission=admission,
        tool_profile_digest_value=_proposal_tool_profile_digest(payload),
    )
    record.update({"token_id_hash": None, "commit_invoked": True, "commit_status": commit["status"], "required_event_digests": _finalize_session(session_id, trace_id, request_id)})
    return record


def _run_approval_scenario(response: dict[str, Any]) -> dict[str, Any]:
    session_id = "ns-live-approval"
    trace_id = "trace-approval-001"
    request_id = "req-approval-001"
    proposal = dict(response["proposal"])
    payload = dict(proposal.get("payload") or {})
    projection = _projection(session_id, trace_id, request_id, "fs.write_patch")
    admission = admit_proposal_v1({**_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id), "proposal": proposal})
    approval_id = str(admission.get("approval_id") or "")
    approval = decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes="live-evidence approval")
    commit = commit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": admission["proposal_digest"],
            "admission_decision_digest": admission["decision_digest"],
            "approval_id": approval_id,
            "execution_result_digest": "2" * 64,
        }
    )
    record = _scenario_base(
        name="approval_required",
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        projection=projection,
        admission=admission,
        tool_profile_digest_value=_proposal_tool_profile_digest(payload),
    )
    record.update(
        {
            "approval_id": approval_id,
            "token_id_hash": None,
            "approval_status": approval["approval"]["status"],
            "commit_invoked": True,
            "commit_status": commit["status"],
            "required_event_digests": _finalize_session(session_id, trace_id, request_id),
            "operator_surfaces": _operator_surface_snapshot(session_id=session_id, trace_id=trace_id, approval_id=approval_id),
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
    admission = admit_proposal_v1({**_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id), "proposal": proposal})
    approval_id = str(admission.get("approval_id") or "")
    approval = decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes="live-evidence approval")
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
    os.environ["ORKET_USE_TOOL_PROFILE_RESOLVER"] = "true"
    os.environ.pop("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", None)
    reset_runtime_state_for_tests()
    adapter = OpenClawJsonlSubprocessAdapter(command=[sys.executable, "tools/fake_openclaw_adapter_strict.py"], io_timeout_seconds=15.0)
    requests = [
        {"type": "next_action", "scenario_kind": "blocked_destructive"},
        {"type": "next_action", "scenario_kind": "approval_required"},
        {"type": "next_action", "scenario_kind": "credentialed_token"},
        {"type": "next_action", "scenario_kind": "credentialed_token_replay"},
    ]
    adapter_result = await adapter.run_requests(requests)
    if not adapter_result.ok:
        raise RuntimeError(
            f"fake OpenClaw adapter failed after {adapter_result.completed_count} responses: {adapter_result.error}"
        )
    responses = adapter_result.responses
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
        "policy_flag_mode": "resolver_canonical",
        "adapter_run": {
            "mode": "subprocess_jsonl",
            "path": "primary",
            "command": [sys.executable, "tools/fake_openclaw_adapter_strict.py"],
            "request_count": len(requests),
            "response_count": len(responses),
            "completed_count": adapter_result.completed_count,
            "failed_at": adapter_result.failed_at,
            "status": "ok",
        },
        "required_event_types": REQUIRED_EVENT_TYPES,
        "scenarios": scenarios,
    }


async def main() -> int:
    artifact = await _run_live()
    await asyncio.to_thread(write_payload_with_diff_ledger, OUTPUT_PATH, artifact)
    print(str(OUTPUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
