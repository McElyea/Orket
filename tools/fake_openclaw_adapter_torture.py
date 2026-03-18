#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
import uuid
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


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
        payload = json.loads(line)
    except json.JSONDecodeError:
        return {"type": "error", "code": "INVALID_JSON", "message": "input line is not valid JSON"}
    if not isinstance(payload, dict):
        return {"type": "error", "code": "INVALID_PAYLOAD", "message": "input must be a JSON object"}
    return payload


def _resolve_corpus_path(path_value: str | None) -> Path:
    root = _project_root()
    raw = str(path_value or "benchmarks/scenarios/nervous_system_attack_corpus.json").strip()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("corpus_path must stay inside repository root")
    return candidate


def _load_cases(corpus_path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("attack corpus must include a cases list")
    by_id: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = str(case.get("id") or "").strip()
        if not case_id:
            continue
        by_id[case_id] = case
    if not by_id:
        raise ValueError("attack corpus has no valid cases")
    return by_id


def _proposal_envelope(
    *,
    session_id: str,
    trace_id: str,
    request_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "proposal_id": str(uuid.uuid4()),
        "proposal_type": "action.tool_call",
        "created_at": _now_utc(),
        "source": {
            "source_id": "fake-openclaw-adapter-torture",
            "source_type": "agent_adapter",
            "trust_tier": "untrusted",
            "model": {"provider": "local", "name": "fake-attack-brain", "version": "0.1"},
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


def _build_response(
    *,
    case: dict[str, Any],
    session_id: str,
    trace_id: str,
    request_id: str,
) -> dict[str, Any]:
    case_id = str(case.get("id") or "")
    payload = dict(case.get("payload") or {})
    response = {
        "type": "action_proposal",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
        "scenario_kind": case_id,
        "proposal": _proposal_envelope(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            payload=payload,
        ),
    }
    token_request = case.get("token_request")
    if isinstance(token_request, dict):
        response["token_request"] = dict(token_request)
    result_payload = case.get("result_payload")
    if isinstance(result_payload, str):
        response["result_payload"] = result_payload
    expected_commit_status = case.get("expected_commit_status")
    if isinstance(expected_commit_status, str) and expected_commit_status.strip():
        response["expected_commit_status"] = expected_commit_status.strip()
    return response


def _select_case_id(request: dict[str, Any], known_case_ids: list[str]) -> str:
    requested = str(request.get("case_id") or request.get("scenario_kind") or "").strip()
    if requested:
        return requested
    if not known_case_ids:
        return ""
    return known_case_ids[0]


def main() -> int:
    try:
        corpus_path = _resolve_corpus_path(None)
        cases_by_id = _load_cases(corpus_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        _write_line({"type": "error", "code": "CORPUS_LOAD_FAILED", "message": str(exc)})
        return 1

    known_case_ids = sorted(cases_by_id.keys())
    while True:
        request = _read_line()
        if request is None:
            return 0

        message_type = str(request.get("type") or "").strip().lower()
        if message_type == "end":
            _write_line({"type": "ended", "status": "ok"})
            return 0
        if message_type not in {"next_action", "next_attack", "action_proposal_request"}:
            _write_line(
                {
                    "type": "error",
                    "code": "UNSUPPORTED_MESSAGE_TYPE",
                    "message": "supported: next_action, next_attack, action_proposal_request, end",
                }
            )
            continue

        case_id = _select_case_id(request, known_case_ids)
        if not case_id:
            _write_line({"type": "error", "code": "NO_CASES_LOADED", "message": "Corpus is empty."})
            continue
        case = cases_by_id.get(case_id)
        if case is None:
            _write_line(
                {
                    "type": "error",
                    "code": "UNKNOWN_CASE_ID",
                    "message": f"unknown case_id: {case_id}",
                    "known_case_ids": known_case_ids,
                }
            )
            continue

        session_id = str(request.get("session_id") or f"torture-{case_id}").strip()
        trace_id = str(request.get("trace_id") or f"trace-{uuid.uuid4().hex[:8]}").strip()
        request_id = str(request.get("request_id") or f"req-{case_id}").strip()
        _write_line(
            _build_response(
                case=case,
                session_id=session_id,
                trace_id=trace_id,
                request_id=request_id,
            )
        )


if __name__ == "__main__":
    raise SystemExit(main())
