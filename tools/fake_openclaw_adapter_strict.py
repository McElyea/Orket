#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_line(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _read_line() -> dict[str, Any] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        parsed = json.loads(line)
    except json.JSONDecodeError:
        return {"type": "error", "code": "INVALID_JSON", "message": "input line is not valid JSON"}
    if not isinstance(parsed, dict):
        return {"type": "error", "code": "INVALID_PAYLOAD", "message": "input must be a JSON object"}
    return parsed


def _build_proposal(
    *,
    session_id: str,
    trace_id: str,
    request_id: str,
    scenario_kind: str,
) -> dict[str, Any]:
    payload = {
        "tool_name": "demo.tool",
        "args": {},
        "schema_valid": True,
        "leak_detected": False,
        "risk_class": "low",
    }

    token_request: dict[str, Any] | None = None
    if scenario_kind == "blocked_destructive":
        payload.update(
            {
                "tool_name": "fs.delete",
                "args": {"path": "./workspace/important.txt"},
                "risk_class": "critical",
                "scope_violation": True,
            }
        )
    elif scenario_kind == "approval_required":
        payload.update(
            {
                "tool_name": "fs.write_patch",
                "args": {"path": "./workspace/notes.md", "patch": "ADD LINE hello"},
                "risk_class": "high",
                "approval_required_destructive": True,
            }
        )
    elif scenario_kind in {"credentialed_token", "credentialed_token_replay"}:
        payload.update(
            {
                "tool_name": "demo.credentialed_echo",
                "args": {"credential_alias": "demo_secret", "message": "hello"},
                "risk_class": "high",
                "approval_required_credentialed": True,
            }
        )
        token_request = {
            "tool_name": "demo.credentialed_echo",
            "scope_json": {"allow": ["credentialed_echo.use"], "ttl_seconds": 60},
            "tool_profile_definition": {"tool": "demo.credentialed_echo", "exfil": False, "risk": "high"},
        }
    else:
        payload["policy_forbidden"] = True
        payload["risk_class"] = "high"

    proposal = {
        "proposal_id": str(uuid.uuid4()),
        "proposal_type": "action.tool_call",
        "created_at": _now_utc(),
        "source": {
            "source_id": "fake-openclaw-adapter",
            "source_type": "agent_adapter",
            "trust_tier": "untrusted",
            "model": {"provider": "local", "name": "fake-brain", "version": "0.1"},
        },
        "context": {
            "projection_pack_digest": "stub",
            "canonical_state_digest": "stub",
            "contract_digest": "stub",
            "policy_digest": "stub",
            "request_id": request_id,
            "trace_id": trace_id,
            "session_id": session_id,
        },
        "payload": payload,
    }
    response = {
        "type": "action_proposal",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "scenario_kind": scenario_kind,
        "proposal": proposal,
    }
    if token_request is not None:
        response["token_request"] = token_request
    return response


def main() -> int:
    while True:
        request = _read_line()
        if request is None:
            return 0

        message_type = str(request.get("type") or "").strip().lower()
        if message_type == "end":
            _write_line({"type": "ended", "status": "ok"})
            return 0

        if message_type not in {"next_action", "action_proposal_request"}:
            _write_line(
                {
                    "type": "error",
                    "code": "UNSUPPORTED_MESSAGE_TYPE",
                    "message": "supported: next_action, action_proposal_request, end",
                }
            )
            continue

        session_id = str(request.get("session_id") or "dev-session").strip() or "dev-session"
        trace_id = str(request.get("trace_id") or f"trace-{uuid.uuid4().hex[:8]}").strip()
        request_id = str(request.get("request_id") or "fake-run").strip() or "fake-run"
        scenario_kind = str(request.get("scenario_kind") or request.get("scenario") or "").strip().lower()
        if not scenario_kind:
            scenario_kind = "blocked_destructive"

        _write_line(
            _build_proposal(
                session_id=session_id,
                trace_id=trace_id,
                request_id=request_id,
                scenario_kind=scenario_kind,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
