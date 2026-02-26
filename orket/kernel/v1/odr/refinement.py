from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Sequence


REQUIRED_REQUIREMENT_SECTIONS: tuple[str, ...] = (
    "## Scope",
    "## Definitions",
    "## Non-goals",
    "## Invariants",
    "## Failure Codes",
    "## Acceptance Tests",
    "## Change Log",
)

CONSTRAINTS_BLOCK_RE = re.compile(r"```orket-constraints\s*(\{.*?\})\s*```", re.DOTALL)


def extract_constraints_ledger(requirement_markdown: str) -> Dict[str, Any]:
    match = CONSTRAINTS_BLOCK_RE.search(str(requirement_markdown or ""))
    if match is None:
        return {}
    payload = match.group(1)
    return json.loads(payload)


def missing_required_sections(requirement_markdown: str) -> List[str]:
    text = str(requirement_markdown or "")
    return [section for section in REQUIRED_REQUIREMENT_SECTIONS if section not in text]


def carry_forward_gaps(previous_ledger: Dict[str, Any], next_ledger: Dict[str, Any]) -> List[str]:
    previous_ids = _must_have_ids(previous_ledger)
    next_ids = _must_have_ids(next_ledger)
    removed_ids = _removed_ids(next_ledger)
    return sorted(
        identifier for identifier in previous_ids if identifier not in next_ids and identifier not in removed_ids
    )


def auditor_incorporation_gaps(auditor_issues: Sequence[Dict[str, Any]], next_ledger: Dict[str, Any]) -> List[str]:
    resolution_by_issue: Dict[str, Dict[str, Any]] = {}
    for row in _as_list(next_ledger.get("auditor_resolution")):
        issue_id = str(row.get("issue_id") or "").strip()
        if issue_id:
            resolution_by_issue[issue_id] = row

    must_have = _must_have_ids(next_ledger)
    decision_required = _decision_required_ids(next_ledger)
    missing: List[str] = []
    for issue in auditor_issues:
        issue_id = str(issue.get("id") or "").strip()
        if not issue_id:
            continue
        resolution = resolution_by_issue.get(issue_id)
        if resolution is None:
            missing.append(issue_id)
            continue
        status = str(resolution.get("status") or "").strip().lower()
        if status not in {"addressed", "declined", "decision_required"}:
            missing.append(issue_id)
            continue
        if status == "addressed":
            clause_id = str(resolution.get("clause_id") or "").strip()
            if not clause_id or clause_id not in must_have:
                missing.append(issue_id)
        if status == "decision_required":
            decision_id = str(resolution.get("decision_id") or "").strip()
            if not decision_id or decision_id not in decision_required:
                missing.append(issue_id)
        if status == "declined":
            rationale = str(resolution.get("rationale") or "").strip()
            if not rationale:
                missing.append(issue_id)
    return sorted(set(missing))


def forbidden_pattern_hits(requirement_markdown: str, forbidden_patterns: Iterable[str]) -> List[str]:
    text = strip_constraints_block(requirement_markdown)
    hits: List[str] = []
    for pattern in forbidden_patterns:
        if re.search(pattern, text, re.IGNORECASE) is not None:
            hits.append(pattern)
    return sorted(set(hits))


def unresolved_issue_count(issues: Sequence[Dict[str, Any]]) -> int:
    count = 0
    for issue in issues:
        status = str(issue.get("status") or "").strip().lower()
        if status in {"", "open", "unresolved"}:
            count += 1
    return count


def reopened_issues(issue_series: Sequence[Sequence[Dict[str, Any]]]) -> List[str]:
    resolved_once: set[str] = set()
    reopened: set[str] = set()
    for snapshot in issue_series:
        for issue in snapshot:
            issue_id = str(issue.get("id") or "").strip()
            if not issue_id:
                continue
            status = str(issue.get("status") or "").strip().lower()
            reopened_from = str(issue.get("reopened_from") or "").strip()
            if status == "resolved":
                resolved_once.add(issue_id)
            if status in {"open", "unresolved"} and issue_id in resolved_once and not reopened_from:
                reopened.add(issue_id)
    return sorted(reopened)


def non_increasing(values: Sequence[int]) -> bool:
    if not values:
        return True
    for idx in range(1, len(values)):
        if values[idx] > values[idx - 1]:
            return False
    return True


def strip_constraints_block(requirement_markdown: str) -> str:
    return CONSTRAINTS_BLOCK_RE.sub("", str(requirement_markdown or ""))


def decision_required_ids(ledger: Dict[str, Any]) -> List[str]:
    return sorted(_decision_required_ids(ledger))


def numeric_day_values(text: str) -> List[str]:
    return sorted(set(re.findall(r"\b\d+\s*days?\b", str(text or ""), flags=re.IGNORECASE)))


def _must_have_ids(ledger: Dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    for row in _as_list(ledger.get("must_have")):
        if isinstance(row, dict):
            value = str(row.get("id") or "").strip()
            if value:
                identifiers.add(value)
    return identifiers


def _removed_ids(ledger: Dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    for row in _as_list(ledger.get("removed")):
        if isinstance(row, dict):
            value = str(row.get("id") or "").strip()
            reason = str(row.get("reason") or "").strip()
            if value and reason:
                identifiers.add(value)
    return identifiers


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []


def _decision_required_ids(ledger: Dict[str, Any]) -> set[str]:
    identifiers: set[str] = set()
    for row in _as_list(ledger.get("decision_required")):
        if isinstance(row, dict):
            value = str(row.get("id") or "").strip()
            if value:
                identifiers.add(value)
    return identifiers
