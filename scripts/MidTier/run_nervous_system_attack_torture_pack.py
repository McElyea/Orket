from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orket.adapters.execution import OpenClawJsonlSubprocessAdapter  # noqa: E402
from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1, commit_proposal_v1, projection_pack_v1  # noqa: E402
from orket.kernel.v1.nervous_system_runtime_extensions import (  # noqa: E402
    consume_credential_token_v1,
    decide_approval_v1,
    get_session_ledger_events_v1,
    issue_credential_token_v1,
)
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests, utc_iso_now  # noqa: E402

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
    "commit.recorded",
]

DEFAULT_CORPUS_PATH = Path("benchmarks/scenarios/nervous_system_attack_corpus.json")
DEFAULT_OUTPUT_PATH = Path("benchmarks/results/nervous_system_attack_torture_evidence.json")


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("attack corpus must include a cases array")
    return [dict(case) for case in cases if isinstance(case, dict)]


def _base_request(*, session_id: str, trace_id: str, request_id: str) -> dict[str, str]:
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
    }


def _collect_event_digests(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_type = {event_type: [] for event_type in REQUIRED_EVENT_TYPES}
    for event in events:
        event_type = str(event.get("event_type") or "")
        digest = str(event.get("event_digest") or "")
        if event_type in by_type and digest:
            by_type[event_type].append(digest)
    return by_type


def _run_projection(*, session_id: str, trace_id: str, request_id: str, tool_name: str) -> dict[str, Any]:
    return projection_pack_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "purpose": "action_path",
            "tool_context_summary": {"tool": tool_name},
            "policy_context": {"mode": "strict"},
        }
    )


def _maybe_approve(admission: dict[str, Any]) -> str | None:
    if str(admission["admission_decision"]["decision"]) != "NEEDS_APPROVAL":
        return None
    approval_id = str(admission.get("approval_id") or "")
    decide_approval_v1(
        approval_id=approval_id,
        decision="approve",
        edited_proposal=None,
        notes="torture-pack auto approval",
    )
    return approval_id


def _run_token_checks(
    *,
    case: dict[str, Any],
    session_id: str,
    trace_id: str,
    request_id: str,
    proposal_digest: str,
    decision_digest: str,
    approval_id: str | None,
) -> dict[str, Any]:
    token_request = case.get("token_request")
    if not isinstance(token_request, dict):
        return {}

    issued = issue_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal_digest": proposal_digest,
            "admission_decision_digest": decision_digest,
            "approval_id": approval_id,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_definition": token_request["tool_profile_definition"],
            "expires_in_seconds": 60,
        }
    )
    first = consume_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "token": issued["token"],
            "proposal_digest": proposal_digest,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    replay = consume_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "token": issued["token"],
            "proposal_digest": proposal_digest,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    return {
        "token_id_hash": issued["token_id_hash"],
        "scope_digest": issued["scope_digest"],
        "first_consume_ok": bool(first.get("ok")),
        "replay_ok": bool(replay.get("ok")),
        "replay_reason_code": str(replay.get("reason_code") or ""),
    }


def _commit_case(
    *,
    case: dict[str, Any],
    admission: dict[str, Any],
    session_id: str,
    trace_id: str,
    request_id: str,
    approval_id: str | None,
) -> dict[str, Any]:
    case_id = str(case.get("id") or "case")
    payload: dict[str, Any] = {
        **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
        "proposal_digest": admission["proposal_digest"],
        "admission_decision_digest": admission["decision_digest"],
        "execution_result_digest": hashlib.sha256(case_id.encode("utf-8")).hexdigest(),
    }
    if approval_id:
        payload["approval_id"] = approval_id
    result_payload = case.get("result_payload")
    if isinstance(result_payload, str):
        payload["execution_result_payload"] = result_payload
        payload["block_result_leaks"] = False
    return commit_proposal_v1(payload)


def _expected_commit_status(case: dict[str, Any], admission_decision: str) -> str:
    explicit = str(case.get("expected_commit_status") or "").strip()
    if explicit:
        return explicit
    if admission_decision == "REJECT":
        return "REJECTED_POLICY"
    return "COMMITTED"


def _scenario_result(
    *,
    case: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(case.get("id") or "")
    expected = dict(case.get("expected") or {})
    session_id = str(response.get("session_id") or f"sess-{case_id}")
    trace_id = str(response.get("trace_id") or f"trace-{case_id}")
    request_id = str(response.get("request_id") or f"req-{case_id}")

    proposal = dict(response.get("proposal") or {})
    payload = dict(proposal.get("payload") or {})
    _ = _run_projection(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        tool_name=str(payload.get("tool_name") or "unknown"),
    )
    admission = admit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id=request_id),
            "proposal": proposal,
        }
    )

    actual_decision = str(admission["admission_decision"]["decision"])
    actual_reasons = list(admission["admission_decision"]["reason_codes"])
    expected_reasons = list(expected.get("reason_codes") or [])
    approval_id = _maybe_approve(admission)
    token_checks = _run_token_checks(
        case=case,
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        proposal_digest=admission["proposal_digest"],
        decision_digest=admission["decision_digest"],
        approval_id=approval_id,
    )
    commit = _commit_case(
        case=case,
        admission=admission,
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        approval_id=approval_id,
    )

    events = get_session_ledger_events_v1(session_id)
    expected_commit = _expected_commit_status(case, actual_decision)
    return {
        "id": case_id,
        "category": str(case.get("category") or ""),
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "expected_decision": str(expected.get("admission_decision") or ""),
        "actual_decision": actual_decision,
        "expected_reason_codes": expected_reasons,
        "actual_reason_codes": actual_reasons,
        "reason_codes_match": actual_reasons == expected_reasons,
        "approval_id": approval_id,
        "token_checks": token_checks,
        "commit_status": commit["status"],
        "expected_commit_status": expected_commit,
        "commit_status_match": str(commit["status"]) == expected_commit,
        "event_digests": _collect_event_digests(events),
    }


async def _run_torture(corpus_path: Path) -> dict[str, Any]:
    os.environ["ORKET_ENABLE_NERVOUS_SYSTEM"] = "true"
    os.environ["ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS"] = "true"
    os.environ["ORKET_USE_TOOL_PROFILE_RESOLVER"] = "false"
    reset_runtime_state_for_tests()

    cases = _load_corpus(corpus_path)
    requests = [
        {
            "type": "next_attack",
            "case_id": str(case.get("id") or ""),
            "session_id": f"ns-torture-{index:03d}",
            "trace_id": f"trace-torture-{index:03d}",
            "request_id": f"req-torture-{index:03d}",
        }
        for index, case in enumerate(cases)
    ]

    adapter = OpenClawJsonlSubprocessAdapter(
        command=[sys.executable, "tools/fake_openclaw_adapter_torture.py"],
        io_timeout_seconds=15.0,
    )
    responses = await adapter.run_requests(requests)
    if len(responses) != len(cases):
        raise RuntimeError("adapter response count mismatch")

    scenarios = [
        _scenario_result(case=case, response=response)
        for case, response in zip(cases, responses, strict=True)
    ]
    passed = [
        item
        for item in scenarios
        if item["actual_decision"] == item["expected_decision"]
        and item["reason_codes_match"]
        and item["commit_status_match"]
    ]
    return {
        "generated_at": utc_iso_now(),
        "corpus_path": corpus_path.as_posix(),
        "adapter_run": {
            "mode": "subprocess_jsonl",
            "path": "primary",
            "command": [sys.executable, "tools/fake_openclaw_adapter_torture.py"],
            "request_count": len(requests),
            "response_count": len(responses),
            "status": "ok",
        },
        "summary": {
            "total_cases": len(scenarios),
            "passed_cases": len(passed),
            "failed_cases": len(scenarios) - len(passed),
        },
        "scenarios": scenarios,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the nervous-system attack torture corpus.")
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS_PATH), help="Path to attack corpus JSON.")
    parser.add_argument("--out", default=str(DEFAULT_OUTPUT_PATH), help="Path to write torture evidence JSON.")
    return parser.parse_args()


async def main() -> int:
    args = _parse_args()
    corpus_path = Path(args.corpus)
    artifact = await _run_torture(corpus_path)

    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(artifact, ensure_ascii=False, indent=2)
    await asyncio.to_thread(output_path.write_text, payload + "\n", "utf-8")
    print(output_path.as_posix())
    return 0 if int(artifact["summary"]["failed_cases"]) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
