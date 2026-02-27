from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SECTION_ORDER = ("REQUIREMENT", "CHANGELOG", "ASSUMPTIONS", "OPEN_QUESTIONS")
DELTA_PRECEDENCE = (
    "constraint_conflict",
    "scope_creep",
    "constraint_remove",
    "constraint_add",
    "constraint_modify",
    "rewrite_same_semantics",
    "formatting_only",
    "no_change",
)
STOPWORDS = {
    "must",
    "shall",
    "required",
    "needs",
    "need",
    "to",
    "is",
    "be",
    "for",
    "the",
    "a",
    "an",
    "and",
    "or",
    "on",
    "of",
    "in",
    "at",
    "by",
    "with",
    "without",
    "not",
    "no",
}
MODAL_PATTERNS = [
    r"\bmust not\b",
    r"\bshall not\b",
    r"\bmay not\b",
    r"\bforbid(?:den)?\b",
    r"\bnever\b",
    r"\bcannot\b",
    r"\bmust\b",
    r"\bshall\b",
    r"\brequired\b",
    r"\bneeds to\b",
    r"\bis required to\b",
    r"\bhas to\b",
    r"\bmay\b",
    r"\bcan\b",
    r"\ballowed\b",
    r"\bpermitted\b",
    r"\bonly\b",
    r"\bat least\b",
    r"\bat most\b",
    r"\bexactly\b",
    r"\bwithin\b",
    r"\bnot exceed\b",
    r"\bprohibited\b",
]
NO_PROHIBITION_PATTERN = re.compile(
    r"^no\s+\w+.*(allowed|permitted|upload|export|outbound|network|cloud)", flags=re.IGNORECASE
)
SECTION_HEADER_PATTERN = re.compile(r"^###\s+(REQUIREMENT|CHANGELOG|ASSUMPTIONS|OPEN_QUESTIONS)\s*$")
CHANGELOG_RESOLVE_PATTERN = re.compile(r"^\s*-?\s*Resolve conflict:\s*(X-[0-9a-f]{10})\s*$", flags=re.IGNORECASE)
REPLACES_PATTERN = re.compile(r"\b(?:Replaces|Supersedes):\s*(C-[0-9a-f]{10})\b", flags=re.IGNORECASE)
DECISION_REQUIRED_PATTERN = re.compile(r"\bDECISION_REQUIRED:\s*([a-zA-Z0-9_]+)", flags=re.IGNORECASE)
STANDARDS = {"gdpr", "hipaa", "aes-256", "tls", "oauth", "sso", "pii", "soc2"}
DOMAIN_ALLOWLIST = {
    "cloud sync",
    "export",
    "backup",
    "multi-user",
    "notifications",
    "telemetry",
    "analytics",
    "sharing",
    "encryption",
    "key management",
    "rotation",
    "remote",
    "server",
    "account",
    "login",
    "audit",
    "forensics",
}
NOUNISH_PATTERN = re.compile(
    r"\b([a-z0-9]+(?:\s+[a-z0-9]+){0,3}\s+(?:data|log|profile|storage|device|api|network|service|encryption|key|retention|window|policy|export|sync|backup))\b",
    flags=re.IGNORECASE,
)
CAMEL_OR_CAPS_PATTERN = re.compile(r"\b([A-Z]{2,20}|[A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")


@dataclass
class Constraint:
    constraint_id: str
    raw: str
    norm: str
    origin: str
    polarity: str
    topic_tokens: set[str]
    replaced_ids: set[str]


def _normalize_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+$", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = re.sub(r"^\s*[\*\u2022]\s+", "- ", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*(\d+)[\.\)]\s+", lambda m: f"{m.group(1)}. ", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*Round:\s*\d+\s*$", "", normalized, flags=re.IGNORECASE | re.MULTILINE)
    return normalized.strip()


def _section_lines(text: str) -> list[str]:
    lines = []
    for raw in _normalize_text(text).split("\n"):
        row = raw.strip()
        if row:
            lines.append(row)
    return lines


def _topic_tokens(text: str) -> set[str]:
    tokens = [token.lower() for token in re.findall(r"[a-zA-Z0-9_]+", text)]
    return {tok for tok in tokens if len(tok) > 2 and tok not in STOPWORDS}


def _is_constraint_candidate(line: str) -> bool:
    if NO_PROHIBITION_PATTERN.search(line):
        return True
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in MODAL_PATTERNS)


def _constraint_polarity(text: str) -> str:
    lowered = text.lower()
    if NO_PROHIBITION_PATTERN.search(lowered):
        return "prohibition"
    if re.search(r"\b(must not|shall not|may not|forbid|forbidden|never|cannot|prohibited)\b", lowered):
        return "prohibition"
    return "obligation"


def _constraint_units(lines: list[str]) -> list[str]:
    units: list[str] = []
    for line in lines:
        if not _is_constraint_candidate(line):
            continue
        parts = [part.strip() for part in re.split(r"[.;]", line) if part.strip()]
        if not parts:
            parts = [line.strip()]
        for part in parts:
            if _is_constraint_candidate(part):
                units.append(part)
    return units


def _extract_constraints(sections: dict[str, str]) -> tuple[list[Constraint], bool]:
    constraints: list[Constraint] = []
    assumption_violation = False
    for section in SECTION_ORDER:
        lines = _section_lines(sections.get(section, ""))
        units = _constraint_units(lines)
        if section == "ASSUMPTIONS" and units:
            assumption_violation = True
        for unit in units:
            norm = _normalize_text(unit)
            cid = "C-" + hashlib.sha256(norm.encode("utf-8")).hexdigest()[:10]
            replaced_ids = {token.upper() for token in REPLACES_PATTERN.findall(unit)}
            constraints.append(
                Constraint(
                    constraint_id=cid,
                    raw=unit,
                    norm=norm,
                    origin=section.lower(),
                    polarity=_constraint_polarity(norm),
                    topic_tokens=_topic_tokens(norm),
                    replaced_ids=replaced_ids,
                )
            )
    return constraints, assumption_violation


def _extract_entities(text: str) -> set[str]:
    norm = _normalize_text(text).lower()
    entities: set[str] = set()
    for token in STANDARDS:
        if token in norm:
            entities.add(token)
    for token in DOMAIN_ALLOWLIST:
        if token in norm:
            entities.add(token)
    for match in NOUNISH_PATTERN.findall(norm):
        entities.add(match.strip().lower())
    for token in CAMEL_OR_CAPS_PATTERN.findall(_normalize_text(text)):
        entities.add(token.lower())
    return entities


def _shingle_jaccard(a: str, b: str, k: int = 3) -> float:
    def _shingles(text: str) -> set[str]:
        words = re.findall(r"[a-z0-9_]+", text.lower())
        if len(words) < k:
            return {" ".join(words)} if words else set()
        return {" ".join(words[i : i + k]) for i in range(0, len(words) - k + 1)}

    sa = _shingles(a)
    sb = _shingles(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(len(sa | sb))


def _diff_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 0.0
    return 1.0 - SequenceMatcher(None, a, b).ratio()


def _conflicting_pairs(constraints: list[Constraint]) -> list[tuple[Constraint, Constraint]]:
    pairs: list[tuple[Constraint, Constraint]] = []
    for i in range(0, len(constraints)):
        for j in range(i + 1, len(constraints)):
            left = constraints[i]
            right = constraints[j]
            if left.polarity == right.polarity:
                continue
            overlap = left.topic_tokens & right.topic_tokens
            if len(overlap) >= 2:
                pairs.append((left, right))
    return pairs


def _conflict_id(ca_id: str, cb_id: str) -> str:
    lo, hi = sorted([ca_id, cb_id])
    return "X-" + hashlib.sha256(f"{lo}:{hi}".encode("utf-8")).hexdigest()[:10]


def _parse_changelog_markers(changelog_text: str) -> set[str]:
    markers: set[str] = set()
    for line in _section_lines(changelog_text):
        match = CHANGELOG_RESOLVE_PATTERN.match(line)
        if match:
            markers.add(match.group(1).upper())
    return markers


def _decision_required_keys(open_questions_text: str) -> set[str]:
    return {token.lower() for token in DECISION_REQUIRED_PATTERN.findall(open_questions_text)}


def _constraint_ids(constraints: list[Constraint]) -> set[str]:
    return {row.constraint_id for row in constraints}


def _scope_creep(current_requirement: str, previous_requirement: str, baseline_scope_text: str) -> tuple[bool, set[str]]:
    current_entities = _extract_entities(current_requirement)
    previous_entities = _extract_entities(previous_requirement)
    baseline_entities = _extract_entities(baseline_scope_text)
    new_entities = current_entities - previous_entities
    new_domain_entities = {token for token in new_entities if token in DOMAIN_ALLOWLIST or token in STANDARDS}
    if len(new_domain_entities) >= 2:
        return True, new_domain_entities
    for token in DOMAIN_ALLOWLIST:
        if token in current_entities and token not in baseline_entities:
            return True, {token}
    return False, new_domain_entities


def _section_delta(
    *,
    prev_text: str,
    cur_text: str,
    prev_constraints: list[Constraint],
    cur_constraints: list[Constraint],
    is_requirement: bool,
    baseline_scope_text: str,
) -> str:
    prev_norm = _normalize_text(prev_text)
    cur_norm = _normalize_text(cur_text)
    if prev_norm == cur_norm:
        return "no_change"

    prev_ids = _constraint_ids(prev_constraints)
    cur_ids = _constraint_ids(cur_constraints)
    added = cur_ids - prev_ids
    removed = prev_ids - cur_ids

    if is_requirement:
        creep, _ = _scope_creep(cur_norm, prev_norm, baseline_scope_text)
        if creep:
            return "scope_creep"

    cur_conflicts = _conflicting_pairs(cur_constraints)
    if cur_conflicts:
        return "constraint_conflict"
    if removed and added:
        return "constraint_modify"
    if removed:
        return "constraint_remove"
    if added:
        return "constraint_add"

    prev_tokens = re.findall(r"[a-z0-9_]+", prev_norm.lower())
    cur_tokens = re.findall(r"[a-z0-9_]+", cur_norm.lower())
    if sorted(prev_tokens) == sorted(cur_tokens):
        return "formatting_only"

    prev_entities = _extract_entities(prev_norm)
    cur_entities = _extract_entities(cur_norm)
    if len(cur_entities - prev_entities) <= 1 and _shingle_jaccard(prev_norm, cur_norm, 3) >= 0.55:
        return "rewrite_same_semantics"
    return "constraint_modify"


def _round_label(section_labels: dict[str, str], conflict_active: bool) -> str:
    if conflict_active:
        return "constraint_conflict"
    labels = set(section_labels.values())
    for label in DELTA_PRECEDENCE:
        if label in labels:
            return label
    return "no_change"


def evaluate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    runs_out: list[dict[str, Any]] = []
    for run in bundle.get("runs", []):
        rounds = sorted(list(run.get("rounds", [])), key=lambda row: int(row.get("t", 0)))
        if not rounds:
            continue
        first_round = rounds[0]
        first_sections = first_round.get("sections", {}) if isinstance(first_round.get("sections"), dict) else {}
        baseline_scope_text = str(first_sections.get("REQUIREMENT", ""))
        previous_sections = {section: "" for section in SECTION_ORDER}
        previous_constraints_by_section: dict[str, list[Constraint]] = {section: [] for section in SECTION_ORDER}
        requirement_history: list[str] = []
        stable_run_length = 0
        active_conflicts: set[str] = set()
        round_rows: list[dict[str, Any]] = []
        stop_reason = None

        unresolved_issues = set()
        for seeded in run.get("seed_issues", []):
            if isinstance(seeded, str) and seeded.strip():
                unresolved_issues.add(seeded.strip())
        for row in rounds:
            sections_raw = row.get("sections", {}) if isinstance(row.get("sections"), dict) else {}
            section_texts = {section: str(sections_raw.get(section, "")) for section in SECTION_ORDER}
            parse_ok = bool(row.get("parse_ok", True))
            code_leak_hit = bool(row.get("code_leak_hit", False))

            section_constraints: dict[str, list[Constraint]] = {}
            assumption_violation = False
            all_constraints: list[Constraint] = []
            for section in SECTION_ORDER:
                constraints, flagged = _extract_constraints({section: section_texts[section]})
                section_constraints[section] = constraints
                all_constraints.extend(constraints)
                assumption_violation = assumption_violation or flagged

            section_labels: dict[str, str] = {}
            for section in SECTION_ORDER:
                section_labels[section] = _section_delta(
                    prev_text=previous_sections[section],
                    cur_text=section_texts[section],
                    prev_constraints=previous_constraints_by_section[section],
                    cur_constraints=section_constraints[section],
                    is_requirement=section == "REQUIREMENT",
                    baseline_scope_text=baseline_scope_text,
                )

            conflict_pairs = _conflicting_pairs(all_constraints)
            current_conflict_ids = {
                _conflict_id(left.constraint_id, right.constraint_id) for left, right in conflict_pairs
            }
            active_conflicts |= current_conflict_ids

            markers = _parse_changelog_markers(section_texts["CHANGELOG"])
            replaced_ids = set().union(*(c.replaced_ids for c in all_constraints))
            warnings: list[str] = []
            cleared_ids: set[str] = set()
            for conflict_id in sorted(active_conflicts):
                if conflict_id in current_conflict_ids:
                    continue
                if conflict_id in markers:
                    cleared_ids.add(conflict_id)
                    continue
                # Replacement clear fallback: if one side replaced and not present.
                # Telemetry-first warning when marker is missing.
                if replaced_ids:
                    cleared_ids.add(conflict_id)
                    continue
                warnings.append(f"WARN_CONFLICT_CLEAR_MARKER_MISSING:{conflict_id}")
            active_conflicts -= cleared_ids
            conflict_active = bool(active_conflicts)

            requirement_norm = _normalize_text(section_texts["REQUIREMENT"])
            if requirement_history:
                diff_ratio = _diff_ratio(requirement_history[-1], requirement_norm)
                sim_prev = _shingle_jaccard(requirement_history[-1], requirement_norm, 3)
            else:
                diff_ratio = 1.0 if requirement_norm else 0.0
                sim_prev = 0.0
            if len(requirement_history) >= 2:
                sims = [_shingle_jaccard(requirement_history[i], requirement_norm, 3) for i in range(0, len(requirement_history))]
                sim_loop = max(sims) if sims else 0.0
                argmax_loop_index = sims.index(sim_loop) if sims else None
            else:
                sim_loop = 0.0
                argmax_loop_index = None
            requirement_history.append(requirement_norm)

            is_stable = diff_ratio <= 0.05 + 0.02 and sim_prev >= 1.0 - (0.05 + 0.02)
            if is_stable:
                stable_run_length += 1
            else:
                stable_run_length = 0

            decision_keys = {str(k).lower(): v for k, v in dict(run.get("seed_decisions", {})).items()}
            required_decision_keys = _decision_required_keys(section_texts["OPEN_QUESTIONS"])
            resolved_decisions: dict[str, bool] = {}
            for key, value in decision_keys.items():
                value_non_null = value is not None
                value_ref = str(value).lower() in requirement_norm.lower() if value_non_null else False
                key_required = key in required_decision_keys
                resolved_decisions[key] = bool(value_non_null and value_ref and not key_required)
            unresolved_decision_count = sum(1 for ok in resolved_decisions.values() if not ok)

            for note in row.get("notes", []):
                if isinstance(note, str) and note.startswith("issue_closed:"):
                    unresolved_issues.discard(note.split(":", 1)[1].strip())
                if isinstance(note, str) and note.startswith("issue_open:"):
                    unresolved_issues.add(note.split(":", 1)[1].strip())
            unresolved_issue_count = len(unresolved_issues)

            stop_candidate = None
            if parse_ok is False or code_leak_hit is True:
                stop_reason = "FORMAT_VIOLATION"
            elif sim_loop >= 0.65 and argmax_loop_index is not None and argmax_loop_index != len(requirement_history) - 2:
                stop_reason = "LOOP_DETECTED"
            elif stable_run_length >= 2:
                if unresolved_decision_count > 0:
                    stop_candidate = "STOP_CANDIDATE_STABLE_BUT_UNRESOLVED_DECISION"
                elif unresolved_issue_count > 0:
                    stop_candidate = "STOP_CANDIDATE_STABLE_BUT_UNRESOLVED_ISSUE_SOFT_BLOCK"
                else:
                    stop_reason = "CONVERGED_RESOLVED"

            round_label = _round_label(section_labels, conflict_active=conflict_active)
            round_rows.append(
                {
                    "t": int(row.get("t", 0)),
                    "delta_type_by_section": section_labels,
                    "delta_type_round": round_label,
                    "conflict_active": conflict_active,
                    "conflict_ids": sorted(active_conflicts),
                    "warnings": warnings,
                    "parse_ok": parse_ok,
                    "code_leak_hit": code_leak_hit,
                    "assumption_constraint_violation": assumption_violation,
                    "metrics": {
                        "diff_ratio": diff_ratio,
                        "sim_prev": sim_prev,
                        "sim_loop": sim_loop,
                        "argmax_loop_index": argmax_loop_index,
                        "stable_run_length": stable_run_length,
                        "unresolved_decision_count": unresolved_decision_count,
                        "unresolved_issue_count": unresolved_issue_count,
                        "decision_required_count": len(required_decision_keys),
                    },
                    "resolved_decisions": resolved_decisions,
                    "stop_candidate": stop_candidate,
                }
            )
            previous_sections = section_texts
            previous_constraints_by_section = section_constraints
            if stop_reason in {"FORMAT_VIOLATION", "LOOP_DETECTED", "CONVERGED_RESOLVED"}:
                break

        if stop_reason is None:
            last = round_rows[-1]
            unresolved_decisions = int(last["metrics"]["unresolved_decision_count"])
            unresolved_issues_count = int(last["metrics"]["unresolved_issue_count"])
            if unresolved_decisions > 0 or unresolved_issues_count > 0:
                stop_reason = "CONVERGED_UNRESOLVED"
            else:
                stop_reason = "MAX_ROUNDS"

        runs_out.append(
            {
                "run_id": run.get("run_id"),
                "scenario_id": run.get("scenario_id"),
                "category": run.get("category"),
                "model_matrix": run.get("model_matrix"),
                "rounds": round_rows,
                "final_outcome_eval": stop_reason,
            }
        )

    return {
        "schema_version": "odr.calibration.eval.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "run_count": len(runs_out),
        "runs": runs_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate ODR calibration bundle with telemetry-first convergence diagnostics.")
    parser.add_argument("--bundle", default="benchmarks/odr_calibration/candidate_runs_v1.json")
    parser.add_argument("--out", default="benchmarks/odr_calibration/evaluation_v1.json")
    args = parser.parse_args()

    bundle_path = Path(args.bundle)
    out_path = Path(args.out)
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    report = evaluate_bundle(payload)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} (runs={report['run_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
