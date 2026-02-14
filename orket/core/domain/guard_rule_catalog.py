from __future__ import annotations

from typing import Iterable, List


DEFAULT_GUARD_RULE_IDS: List[str] = [
    "HALLUCINATION.FILE_NOT_FOUND",
    "HALLUCINATION.API_NOT_DECLARED",
    "HALLUCINATION.CONTEXT_NOT_PROVIDED",
    "HALLUCINATION.INVENTED_DETAIL",
    "HALLUCINATION.CONTRADICTION",
    "SECURITY.PATH_TRAVERSAL",
    "CONSISTENCY.OUTPUT_FORMAT",
]


def normalize_rule_ids(values: Iterable[object] | None) -> List[str]:
    if values is None:
        return []
    normalized: List[str] = []
    seen = set()
    for value in values:
        rule_id = str(value or "").strip()
        if not rule_id:
            continue
        if rule_id in seen:
            continue
        seen.add(rule_id)
        normalized.append(rule_id)
    return normalized


def ownership_conflicts(prompt_rule_ids: Iterable[object] | None, runtime_guard_rule_ids: Iterable[object] | None) -> List[str]:
    prompt_ids = set(normalize_rule_ids(prompt_rule_ids))
    runtime_ids = set(normalize_rule_ids(runtime_guard_rule_ids))
    return sorted(prompt_ids.intersection(runtime_ids))
