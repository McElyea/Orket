from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence


_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_NONE_TOKENS = {"none", "n/a", "na", "no open questions", "no open question", "not applicable"}
_DECISION_REQUIRED_RE = re.compile(r"decision_required\s*[\[(]?[a-z0-9_\- .]+[\])\:]?", re.IGNORECASE)
_UNRESOLVED_ALTERNATIVE_RE = re.compile(r"\b(either\b.{1,80}\bor\b|\bdepending on\b)", re.IGNORECASE)
_REQUIRED_SIGNAL_RE = re.compile(
    r"\b(must|required|required to|shall|security|encrypt|retention|retain|delete|days?|hours?|minutes?)\b",
    re.IGNORECASE,
)
_CONTRADICTION_PAIRS_SEMANTIC = (
    ("encrypt", "not encrypt"),
    ("retain", "delete"),
    ("store locally", "upload"),
)
_CONTRADICTION_PAIRS_MODAL: tuple[tuple[str, str], ...] = ()
_CONTRADICTION_PAIRS = _CONTRADICTION_PAIRS_SEMANTIC
_REQUIRED_TOKENS = {"must", "requir", "shall", "security", "encrypt", "retention", "retain", "delet"}
_AUTHORIZATION_STOPWORDS = {"applicable", "clause", "clauses", "incorrect", "remove", "remov", "requirement"}


def classify_patch_classes(patches: Sequence[str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for patch in patches:
        text = str(patch or "").strip()
        if not text:
            continue
        prefix_match = re.match(r"^\[(ADD|REMOVE|REWRITE|DECISION_REQUIRED)\]\s*", text, flags=re.IGNORECASE)
        if prefix_match is not None:
            patch_class = prefix_match.group(1).upper()
        else:
            lowered = text.lower()
            if "decision required" in lowered or "choose" in lowered or "resolve" in lowered:
                patch_class = "DECISION_REQUIRED"
            elif any(token in lowered for token in ("remove", "drop", "eliminate", "skip")):
                patch_class = "REMOVE"
            elif any(token in lowered for token in ("rewrite", "replace", "reword", "clarify")):
                patch_class = "REWRITE"
            else:
                patch_class = "ADD"
        rows.append({"patch_class": patch_class, "text": text})
    return rows


def evaluate_semantic_validity(
    *,
    architect_data: Dict[str, Any],
    auditor_data: Dict[str, Any],
    previous_architect_data: Dict[str, Any] | None,
) -> Dict[str, Any]:
    requirement = str(architect_data.get("requirement") or "").strip()
    assumptions = _meaningful_list(architect_data.get("assumptions"))
    open_questions = _meaningful_list(architect_data.get("open_questions"))
    previous_requirement = str((previous_architect_data or {}).get("requirement") or "").strip()

    patch_classes = classify_patch_classes(auditor_data.get("patches") or [])
    remove_patch_texts = [row["text"] for row in patch_classes if row["patch_class"] == "REMOVE"]
    unresolved_alternatives = _unresolved_alternative_hits(requirement)
    explicit_decisions = _explicit_decision_markers(requirement)
    pending_decisions = [*explicit_decisions, *unresolved_alternatives]
    contradiction_hits = _contradiction_hits(requirement)
    demotion_violations = _constraint_demotion_violations(
        previous_requirement=previous_requirement,
        current_requirement=requirement,
        assumptions=assumptions,
        open_questions=open_questions,
        authorized_removals=remove_patch_texts,
    )
    required_constraint_regressions = _required_constraint_regressions(
        previous_requirement=previous_requirement,
        current_requirement=requirement,
        authorized_removals=remove_patch_texts,
    )

    failures: List[str] = []
    if pending_decisions:
        failures.append("pending_decisions")
    if contradiction_hits:
        failures.append("contradictions")
    if demotion_violations:
        failures.append("constraint_demotion")
    if required_constraint_regressions:
        failures.append("required_constraint_regression")

    return {
        "validity_verdict": "valid" if not failures else "invalid",
        "semantic_failures": failures,
        "pending_decision_count": len(pending_decisions),
        "pending_decisions": pending_decisions,
        "open_questions": open_questions,
        "open_question_count": len(open_questions),
        "contradiction_count": len(contradiction_hits),
        "contradiction_hits": contradiction_hits,
        "constraint_demotion_violations": demotion_violations,
        "required_constraint_regressions": required_constraint_regressions,
        "repair_classes": [row["patch_class"] for row in patch_classes],
        "patch_classes": patch_classes,
    }


def _meaningful_list(value: Any) -> List[str]:
    rows: List[str] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        if text.lower() in _NONE_TOKENS:
            continue
        rows.append(text)
    return rows


def _explicit_decision_markers(text: str) -> List[str]:
    return [match.group(0).strip() for match in _DECISION_REQUIRED_RE.finditer(str(text or ""))]


def _unresolved_alternative_hits(text: str) -> List[str]:
    cleaned = str(text or "")
    hits: List[str] = []
    lowered = cleaned.lower()
    if "either" not in lowered and "depending on" not in lowered:
        return hits
    clauses = _split_clauses(cleaned)
    for index, clause in enumerate(clauses):
        clause_lower = clause.lower()
        previous_clause_lower = clauses[index - 1].lower() if index > 0 else ""
        if _DECISION_REQUIRED_RE.search(clause_lower) is not None:
            continue
        if _DECISION_REQUIRED_RE.search(previous_clause_lower) is not None:
            continue
        if _UNRESOLVED_ALTERNATIVE_RE.search(clause_lower) is not None:
            hits.append(clause)
    return hits


def _contradiction_hits(text: str) -> List[str]:
    """
    Detect requirement contradictions using semantic opposite pairs only.

    Modal pairs like "must" vs "must not" are intentionally excluded until
    clause-scoped subject matching exists; full-text checks produce too many
    false positives in valid multi-constraint requirements.
    """
    lowered = str(text or "").lower()
    hits: List[str] = []
    for positive, negative in _CONTRADICTION_PAIRS_SEMANTIC:
        positive_in_text = _contradiction_phrase_present(positive, lowered.replace(negative, ""))
        negative_in_text = _contradiction_phrase_present(negative, lowered)
        if positive_in_text and negative_in_text:
            hits.append(f"{positive}|{negative}")
    return hits


def _contradiction_phrase_present(phrase: str, text: str) -> bool:
    lowered_phrase = str(phrase or "").strip().lower()
    if not lowered_phrase:
        return False
    if " " not in lowered_phrase:
        return re.search(rf"\b{re.escape(lowered_phrase)}\b", text) is not None
    if lowered_phrase.startswith("not "):
        return lowered_phrase in text
    tokens = tuple(token for token in lowered_phrase.split() if token)
    return all(re.search(rf"\b{re.escape(token)}\b", text) is not None for token in tokens)


def _constraint_demotion_violations(
    *,
    previous_requirement: str,
    current_requirement: str,
    assumptions: Sequence[str],
    open_questions: Sequence[str],
    authorized_removals: Sequence[str] | None = None,
) -> List[str]:
    previous = _required_clauses(previous_requirement)
    current = _required_clauses(current_requirement)
    sidecar = _required_clauses("\n".join([*assumptions, *open_questions]))
    violations: List[str] = []
    for clause in previous:
        if _matches_any(clause, current):
            continue
        if _matches_authorized_removal(clause, authorized_removals):
            continue
        if _matches_any(clause, sidecar):
            violations.append(clause)
    return violations


def _required_constraint_regressions(
    *,
    previous_requirement: str,
    current_requirement: str,
    authorized_removals: Sequence[str] | None = None,
) -> List[str]:
    previous = _required_clauses(previous_requirement)
    current = _required_clauses(current_requirement)
    regressions: List[str] = []
    for clause in previous:
        if _matches_any(clause, current):
            continue
        if _matches_authorized_removal(clause, authorized_removals):
            continue
        if _REQUIRED_SIGNAL_RE.search(clause) is None:
            continue
        regressions.append(clause)
    return regressions


def _required_clauses(text: str) -> List[str]:
    return [clause for clause in _split_clauses(text) if _required_signal_relevant(clause)]


def _required_signal_relevant(text: str) -> bool:
    cleaned = str(text or "").strip()
    if len(cleaned) < 12:
        return False
    if _REQUIRED_SIGNAL_RE.search(cleaned) is not None:
        return True
    if _REQUIRED_TOKENS & _tokens(cleaned):
        return True
    return any(ch.isdigit() for ch in cleaned)


def _split_clauses(text: str) -> List[str]:
    chunks = re.split(r"[\n.;:]+", str(text or ""))
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _matches_any(candidate: str, others: Iterable[str]) -> bool:
    candidate_tokens = _tokens(candidate)
    if len(candidate_tokens) < 3:
        return False
    for other in others:
        other_tokens = _tokens(other)
        if len(other_tokens) < 3:
            continue
        overlap = len(candidate_tokens & other_tokens)
        if overlap >= max(3, min(len(candidate_tokens), len(other_tokens)) - 1):
            return True
        min_tokens = min(len(candidate_tokens), len(other_tokens))
        ratio_threshold = 0.85 if min_tokens <= 5 else 0.7
        if overlap / max(1, min_tokens) >= ratio_threshold:
            return True
    return False


def _tokens(text: str) -> set[str]:
    tokens = {
        _normalize_token(token)
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }
    return {token for token in tokens if token}


def _matches_authorized_removal(clause: str, authorized_removals: Sequence[str] | None) -> bool:
    if not authorized_removals:
        return False
    clause_tokens = _salient_tokens(clause)
    if len(clause_tokens) < 2:
        return False
    for removal in authorized_removals:
        removal_tokens = _salient_tokens(removal)
        if len(removal_tokens) < 2:
            continue
        overlap = 0
        for clause_token in clause_tokens:
            if any(_loosely_matches_token(clause_token, removal_token) for removal_token in removal_tokens):
                overlap += 1
        if overlap >= max(2, min(len(clause_tokens), len(removal_tokens)) - 1):
            return True
    return False


def _salient_tokens(text: str) -> set[str]:
    return {
        token
        for token in _tokens(text)
        if token not in _AUTHORIZATION_STOPWORDS and token not in {"all", "must", "system", "tool"}
    }


def _loosely_matches_token(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) < 5 or len(right) < 5:
        return False
    return left.startswith(right) or right.startswith(left)


def _normalize_token(token: str) -> str:
    value = str(token or "").strip().lower()
    # Minimal suffix stripping heuristic for overlap checks only.
    # Known asymmetry remains: "deletes" -> "delet", while "delete" stays "delete".
    for suffix in ("ing", "ed", "es", "s"):
        if len(value) > len(suffix) + 3 and value.endswith(suffix):
            return value[: -len(suffix)]
    return value
