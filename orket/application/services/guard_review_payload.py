"""Read guard diagnostics from the bound tool call or an existing legacy turn."""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from orket.core.domain.execution import ExecutionTurn
from orket.core.domain.guard_review import GuardReviewPayload


def extract_legacy_guard_review(content: str) -> dict[str, Any]:
    blob = content or ""
    decoder = json.JSONDecoder()
    candidates: list[dict[str, Any]] = []
    for chunk in re.findall(r"```json\s*([\s\S]*?)```", blob, flags=re.IGNORECASE):
        try:
            parsed = json.loads(chunk.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
    start = 0
    while (brace_index := blob.find("{", start)) != -1:
        try:
            parsed, end_pos = decoder.raw_decode(blob[brace_index:])
        except json.JSONDecodeError:
            start = brace_index + 1
            continue
        if isinstance(parsed, dict):
            candidates.append(parsed)
        start = brace_index + max(end_pos, 1)
    for parsed in candidates:
        if {"rationale", "violations", "remediation_actions"} & parsed.keys():
            return parsed
    return {}


def guard_review_for_turn(turn: ExecutionTurn) -> GuardReviewPayload:
    blocked_calls = [call for call in turn.tool_calls if call.tool == "update_issue_status"
                     and str(call.args.get("status", "")).strip().lower() == "blocked"]
    # One rejected decision owns its diagnostics; conflicting decisions have no authority.
    if len(blocked_calls) > 1:
        return GuardReviewPayload()
    if blocked_calls and "guard_review" in blocked_calls[0].args:
        payload = blocked_calls[0].args["guard_review"]
    else:
        payload = extract_legacy_guard_review(turn.content or "")
    try:
        return GuardReviewPayload.model_validate(payload, strict=True)
    except ValidationError:
        # Malformed structured metadata must never fall back to unrelated prose.
        return GuardReviewPayload()
