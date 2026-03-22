from __future__ import annotations

import json
import re
from typing import Any

from orket.kernel.v1.odr.semantic_validity import _matches_any, _required_clauses

_ORKET_CONSTRAINT_BLOCK = re.compile(r"```orket-constraints\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+")
_LIST_PREFIX = re.compile(r"^(?:[-*]\s+|\d+\.\s+)")


def _normalize_clause_text(text: str) -> str:
    value = _LIST_PREFIX.sub("", str(text or "").strip())
    return value.strip()


def _constraint_payload(requirement: str) -> dict[str, Any] | None:
    match = _ORKET_CONSTRAINT_BLOCK.search(str(requirement or ""))
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _constraint_texts(requirement: str, key: str) -> list[str]:
    payload = _constraint_payload(requirement)
    if not isinstance(payload, dict):
        return []
    rows: list[str] = []
    for item in list(payload.get(key) or []):
        if not isinstance(item, dict):
            continue
        text = _normalize_clause_text(str(item.get("text") or ""))
        if text:
            rows.append(text)
    return rows


def _strip_constraint_block(requirement: str) -> str:
    return _ORKET_CONSTRAINT_BLOCK.sub("", str(requirement or ""))


def _section_lines(requirement: str, heading: str) -> list[str]:
    rows: list[str] = []
    in_section = False
    for raw_line in _strip_constraint_block(requirement).splitlines():
        line = str(raw_line).rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if _MARKDOWN_HEADING.match(stripped):
            normalized = _MARKDOWN_HEADING.sub("", stripped).strip().casefold()
            if in_section and normalized != heading.casefold():
                break
            in_section = normalized == heading.casefold()
            continue
        if not in_section:
            continue
        text = _normalize_clause_text(stripped)
        if text:
            rows.append(text)
    return rows


def accepted_decision_summaries(requirement: str) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for text in _constraint_texts(requirement, "must_have"):
        normalized = text.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        rows.append(text)
    for clause in _required_clauses(requirement):
        if "decision_required" in clause.lower():
            continue
        text = _normalize_clause_text(clause)
        if not text or not re.search(r"\b(must|shall|must not|should not|never|prohibited|required)\b", text, re.IGNORECASE):
            continue
        normalized = text.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        rows.append(text)
    return rows


def rejected_path_summaries(requirement: str) -> list[str]:
    return _constraint_texts(requirement, "forbidden")


def invariant_summaries(requirement: str) -> list[str]:
    return _section_lines(requirement, "Invariants")


def unresolved_issue_summaries(*, scenario_input: dict[str, Any], latest_trace: dict[str, Any] | None) -> list[str]:
    if isinstance(latest_trace, dict):
        pending = [str(item).strip() for item in list(latest_trace.get("pending_decisions") or []) if str(item).strip()]
        architect = latest_trace.get("architect_parsed")
        open_questions = []
        if isinstance(architect, dict):
            open_questions = [
                str(item).strip()
                for item in list(architect.get("open_questions") or [])
                if str(item).strip() and str(item).strip().lower() != "- none"
            ]
        rows = [*pending, *open_questions]
        if rows:
            return rows
    issue_rows = []
    for issue in list(scenario_input.get("A0") or []):
        issue_id = str(issue.get("id") or "").strip()
        required_action = str(issue.get("required_action") or "").strip()
        if issue_id or required_action:
            issue_rows.append(f"{issue_id}: {required_action}".strip(": "))
    return issue_rows


def latest_architect_delta(latest_trace: dict[str, Any] | None) -> str:
    if not isinstance(latest_trace, dict):
        return ""
    architect = latest_trace.get("architect_parsed")
    if not isinstance(architect, dict):
        return ""
    changelog = [str(item).strip() for item in list(architect.get("changelog") or []) if str(item).strip()]
    return " | ".join(changelog[:3])


def build_replay_source_history(
    *,
    scenario_input: dict[str, Any],
    current_requirement: str,
    prior_auditor_output: str,
    latest_trace: dict[str, Any] | None,
    round_index: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "artifact_id": f"current_requirement_r{round_index}",
            "artifact_kind": "current_canonical_artifact",
            "authority_level": "authoritative",
            "content": current_requirement,
            "round_index": round_index,
        }
    ]
    for idx, clause in enumerate(accepted_decision_summaries(current_requirement)[:3], start=1):
        rows.append(
            {
                "artifact_id": f"accepted_{idx}_r{round_index}",
                "artifact_kind": "accepted_decision_summary",
                "authority_level": "authoritative",
                "content": clause,
                "round_index": round_index,
            }
        )
    for idx, issue in enumerate(
        unresolved_issue_summaries(scenario_input=scenario_input, latest_trace=latest_trace)[:3],
        start=1,
    ):
        rows.append(
            {
                "artifact_id": f"unresolved_{idx}_r{round_index}",
                "artifact_kind": "unresolved_issue_summary",
                "authority_level": "authoritative",
                "content": issue,
                "round_index": round_index,
            }
        )
    if prior_auditor_output.strip():
        rows.append(
            {
                "artifact_id": f"prior_auditor_r{round_index}",
                "artifact_kind": "latest_auditor_critique",
                "authority_level": "authoritative",
                "content": prior_auditor_output,
                "round_index": round_index,
            }
        )
    delta = latest_architect_delta(latest_trace)
    if delta:
        rows.append(
            {
                "artifact_id": f"latest_architect_delta_r{round_index}",
                "artifact_kind": "latest_architect_delta",
                "authority_level": "authoritative",
                "content": delta,
                "round_index": round_index,
            }
        )
    return rows


def compute_continuity_run_metrics(round_rows: list[dict[str, Any]], final_requirement: str) -> dict[str, Any]:
    contradiction_count = 0
    regression_count = 0
    reopened_decision_count = 0
    previous_pending = 0
    accepted_before_final: list[str] = []
    saw_accepted = False
    for row in round_rows:
        trace = row.get("trace")
        if not isinstance(trace, dict):
            continue
        contradiction_count += int(trace.get("contradiction_count") or 0)
        regression_count += len(trace.get("required_constraint_regressions") or []) + len(
            trace.get("constraint_demotion_violations") or []
        )
        accepted_now = accepted_decision_summaries(str((trace.get("architect_parsed") or {}).get("requirement") or ""))
        if accepted_now:
            saw_accepted = True
        pending_now = int(trace.get("pending_decision_count") or 0)
        if saw_accepted and pending_now > previous_pending:
            reopened_decision_count += pending_now - previous_pending
        previous_pending = pending_now
    for row in round_rows[:-1]:
        trace = row.get("trace")
        if not isinstance(trace, dict):
            continue
        for clause in accepted_decision_summaries(str((trace.get("architect_parsed") or {}).get("requirement") or "")):
            if not _matches_any(clause, accepted_before_final):
                accepted_before_final.append(clause)
    final_clauses = accepted_decision_summaries(final_requirement)
    preserved = sum(1 for clause in accepted_before_final if _matches_any(clause, final_clauses))
    carry_forward_integrity = 1.0 if not accepted_before_final else preserved / len(accepted_before_final)
    return {
        "reopened_decision_count": reopened_decision_count,
        "contradiction_count": contradiction_count,
        "regression_count": regression_count,
        "carry_forward_integrity": round(carry_forward_integrity, 6),
    }
