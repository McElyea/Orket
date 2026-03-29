from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from orket.application.review.bundle_validation import load_validated_review_run_bundle_artifacts
from orket.application.review.control_plane_projection import validate_review_required_identifier
from scripts.reviewrun.score_answer_key_contract import REPORT_CONTRACT_VERSION, validate_answer_key_score_report
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "not",
    "of",
    "on",
    "or",
    "so",
    "such",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "to",
    "use",
    "uses",
    "using",
    "was",
    "when",
    "with",
}


def _load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _json_blob(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _compile_patterns(raw_patterns: List[Any]) -> List[re.Pattern[str]]:
    compiled: List[re.Pattern[str]] = []
    for item in raw_patterns:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            compiled.append(re.compile(text, re.IGNORECASE | re.MULTILINE))
        except re.error:
            compiled.append(re.compile(re.escape(text), re.IGNORECASE | re.MULTILINE))
    return compiled


def _matches_any(patterns: List[re.Pattern[str]], corpus: str) -> bool:
    return any(pattern.search(corpus) for pattern in patterns)


def _matches_file_patterns(patterns: List[Any], changed_paths: List[str]) -> bool:
    for raw in patterns:
        pattern = str(raw or "").strip()
        if not pattern:
            continue
        if any(fnmatch.fnmatch(path, pattern) for path in changed_paths):
            return True
    return False


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _stem_token(token: str) -> str:
    text = str(token or "").strip().lower()
    replacements = {
        "json.loads": "json_loads",
        "rce": "remote_code_execution",
        "non-empty": "nonempty",
        "nonempty": "nonempty",
    }
    text = replacements.get(text, text)
    if len(text) <= 4:
        return text
    suffixes = (
        "izations",
        "ization",
        "ations",
        "ation",
        "ments",
        "ment",
        "ness",
        "tion",
        "sion",
        "able",
        "ible",
        "ally",
        "edly",
        "ingly",
        "ance",
        "ence",
        "ious",
        "ing",
        "ies",
        "ied",
        "ers",
        "er",
        "ed",
        "ly",
        "es",
        "s",
    )
    for suffix in suffixes:
        if len(text) > len(suffix) + 2 and text.endswith(suffix):
            if suffix in {"ies", "ied"}:
                return text[: -len(suffix)] + "y"
            return text[: -len(suffix)]
    return text


def _semantic_tokens(value: str) -> set[str]:
    normalized = _normalize_text(value).replace("_", " ")
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    return {
        _stem_token(token)
        for token in raw_tokens
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _semantic_match(expected: str, actual: str) -> bool:
    expected_tokens = _semantic_tokens(expected)
    actual_tokens = _semantic_tokens(actual)
    if not expected_tokens or not actual_tokens:
        return False
    overlap = expected_tokens & actual_tokens
    overlap_count = len(overlap)
    if overlap_count == 0:
        return False
    expected_count = len(expected_tokens)
    overlap_ratio = overlap_count / float(expected_count)
    if expected_count <= 2:
        return overlap_count == expected_count
    if expected_count == 3:
        return overlap_count >= 2
    return overlap_count >= 2 and overlap_ratio >= 0.34


def _contains_theme(corpus: str, theme: str) -> bool:
    norm = _normalize_text(theme)
    if not norm:
        return False
    token_len = max(5, min(16, len(norm.split())))
    needle = " ".join(norm.split()[:token_len])
    return needle in _normalize_text(corpus)


def _model_review_entries(model: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not isinstance(model, dict):
        return []
    entries: List[Dict[str, Any]] = []
    for index, issue in enumerate(list(model.get("high_risk_issues") or [])):
        if not isinstance(issue, dict):
            continue
        why = str(issue.get("why") or "")
        where = str(issue.get("where") or "")
        impact = str(issue.get("impact") or "")
        suggested_fix = str(issue.get("suggested_fix") or "")
        entries.append(
            {
                "entry_index": index,
                "reasoning_corpus": " ".join(part for part in (why, where, impact) if part),
                "fix_corpus": suggested_fix,
                "full_corpus": " ".join(part for part in (why, where, impact, suggested_fix) if part),
            }
        )
    global_corpus_parts: List[str] = []
    global_corpus_parts.extend(str(item or "") for item in list(model.get("summary") or []))
    global_corpus_parts.extend(str(item or "") for item in list(model.get("missing_tests") or []))
    global_corpus_parts.extend(str(item or "") for item in list(model.get("questions_for_author") or []))
    global_corpus_parts.extend(str(item or "") for item in list(model.get("nits") or []))
    global_corpus_parts.extend(str(item or "") for item in list(model.get("refs") or []))
    global_corpus = " ".join(part for part in global_corpus_parts if str(part).strip())
    if global_corpus:
        entries.append(
            {
                "entry_index": -1,
                "reasoning_corpus": global_corpus,
                "fix_corpus": global_corpus,
                "full_corpus": global_corpus,
            }
        )
    return entries


def _score_model_issue(
    *,
    issue: Dict[str, Any],
    issue_id: str,
    compiled: List[re.Pattern[str]],
    entries: List[Dict[str, Any]],
) -> tuple[bool, int, int]:
    expected_reasoning = [str(item or "") for item in list(issue.get("expected_reasoning") or []) if str(item or "").strip()]
    expected_fix = [str(item or "") for item in list(issue.get("expected_fix") or []) if str(item or "").strip()]
    canonical_why = str(issue.get("why") or "")
    best_hit = False
    best_reason_hits = 0
    best_fix_hits = 0
    best_rank = (-1, -1, -1, -1)

    for entry in entries:
        full_corpus = str(entry.get("full_corpus") or "")
        reasoning_corpus = str(entry.get("reasoning_corpus") or "")
        fix_corpus = str(entry.get("fix_corpus") or "")
        structured_flag = 1 if int(entry.get("entry_index", -1)) >= 0 else 0

        hit = False
        if issue_id and issue_id in full_corpus:
            hit = True
        elif compiled and _matches_any(compiled, full_corpus):
            hit = True
        elif canonical_why and _semantic_match(canonical_why, reasoning_corpus):
            hit = True
        elif any(_semantic_match(bullet, fix_corpus) for bullet in expected_fix):
            hit = True

        reason_hits = 0
        fix_hits = 0
        if hit:
            for bullet in expected_reasoning:
                if _semantic_match(bullet, reasoning_corpus):
                    reason_hits += 1
            if reason_hits == 0 and canonical_why and _semantic_match(canonical_why, reasoning_corpus):
                reason_hits = 1
            for bullet in expected_fix:
                if _semantic_match(bullet, fix_corpus):
                    fix_hits += 1

        rank = (1 if hit else 0, reason_hits, fix_hits, structured_flag)
        if rank > best_rank:
            best_rank = rank
            best_hit = hit
            best_reason_hits = reason_hits
            best_fix_hits = fix_hits

    return best_hit, best_reason_hits, best_fix_hits


def score_answer_key(
    *,
    run_dir: Path,
    answer_key_path: Path,
) -> Dict[str, Any]:
    bundle_artifacts = load_validated_review_run_bundle_artifacts(run_dir)
    manifest = dict(bundle_artifacts.get("manifest") or {})
    snapshot = dict(bundle_artifacts.get("snapshot") or {})
    deterministic = dict(bundle_artifacts.get("deterministic") or {})
    model = dict(model_payload) if isinstance((model_payload := bundle_artifacts.get("model_assisted")), dict) else None
    key = _load_json(answer_key_path)
    run_id = validate_review_required_identifier(
        deterministic.get("run_id") or manifest.get("run_id"),
        error="reviewrun_answer_key_score_run_id_required",
    )

    changed_paths = [str(item.get("path") or "") for item in list(snapshot.get("changed_files") or [])]
    diff_unified = str(snapshot.get("diff_unified") or "")
    finding_text = _json_blob(deterministic.get("findings") or [])
    model_text = _json_blob(model) if isinstance(model, dict) else ""
    review_entries = _model_review_entries(model)

    scoring = dict(key.get("scoring") or {})
    must_weight = int(scoring.get("must_catch_weight") or 5)
    nice_weight = int(scoring.get("nice_catch_weight") or 2)
    reasoning_weight = int(scoring.get("reasoning_weight") or 2)
    fix_weight = int(scoring.get("fix_weight") or 1)

    findings = list(deterministic.get("findings") or [])
    found_tags = set()
    for finding in findings:
        details = finding.get("details") if isinstance(finding, dict) else {}
        tags = details.get("tags") if isinstance(details, dict) else []
        for tag in list(tags or []):
            text = str(tag or "").strip()
            if text:
                found_tags.add(text)

    rows: List[Dict[str, Any]] = []
    det_score = 0
    det_max = 0
    model_score = 0
    model_max = 0
    model_reasoning_score = 0
    model_reasoning_max = 0
    model_fix_score = 0
    model_fix_max = 0

    for issue in list(key.get("issues") or []):
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id") or "")
        compiled = _compile_patterns(list(issue.get("fingerprints") or []))
        files = list(issue.get("files") or [])
        present_in_diff = _matches_any(compiled, diff_unified) if compiled else False
        present_in_paths = _matches_file_patterns(files, changed_paths)
        present = bool(present_in_diff or present_in_paths)
        weight = must_weight if bool(issue.get("must_catch")) else nice_weight
        det_hit = False
        if issue_id and issue_id in found_tags:
            det_hit = True
        elif compiled:
            det_hit = _matches_any(compiled, finding_text)

        reason_hits = 0
        fix_hits = 0
        model_hit = False
        if model_text:
            model_hit, reason_hits, fix_hits = _score_model_issue(
                issue=issue,
                issue_id=issue_id,
                compiled=compiled,
                entries=review_entries,
            )
            if not model_hit:
                if issue_id and issue_id in model_text:
                    model_hit = True
                elif compiled:
                    model_hit = _matches_any(compiled, model_text)
            if reason_hits == 0:
                for bullet in list(issue.get("expected_reasoning") or []):
                    if _contains_theme(model_text, str(bullet or "")):
                        reason_hits += 1
            if fix_hits == 0:
                for bullet in list(issue.get("expected_fix") or []):
                    if _contains_theme(model_text, str(bullet or "")):
                        fix_hits += 1

        row = {
            "issue_id": issue_id,
            "severity": str(issue.get("severity") or ""),
            "must_catch": bool(issue.get("must_catch") or False),
            "present": present,
            "deterministic_hit": bool(det_hit),
            "model_hit": bool(model_hit),
            "reasoning_hits": int(reason_hits),
            "fix_hits": int(fix_hits),
            "weight": int(weight),
        }
        rows.append(row)

        if not present:
            continue
        det_max += weight
        if det_hit:
            det_score += weight
        if model_text:
            model_max += weight
            if model_hit:
                model_score += weight
            model_reasoning_max += reasoning_weight
            if reason_hits > 0:
                model_reasoning_score += reasoning_weight
            model_fix_max += fix_weight
            if fix_hits > 0:
                model_fix_score += fix_weight

    present_rows = [row for row in rows if row["present"]]
    missed_must = [row["issue_id"] for row in present_rows if row["must_catch"] and not row["deterministic_hit"]]
    unexpected_hits = [row["issue_id"] for row in rows if not row["present"] and row["deterministic_hit"]]

    summary = {
        "contract_version": REPORT_CONTRACT_VERSION,
        "fixture_id": str(key.get("fixture_id") or ""),
        "run_id": run_id,
        "run_dir": str(run_dir),
        "answer_key": str(answer_key_path),
        "snapshot_digest": str(snapshot.get("snapshot_digest") or ""),
        "policy_digest": str(deterministic.get("policy_digest") or ""),
        "deterministic": {
            "score": det_score,
            "max_score": det_max,
            "coverage": 0.0 if det_max == 0 else round(det_score / float(det_max), 6),
            "present_issue_count": len(present_rows),
            "missed_must_catch": missed_must,
            "unexpected_hits": unexpected_hits,
        },
        "model_assisted": {
            "enabled": bool(model_text),
            "score": model_score,
            "max_score": model_max,
            "coverage": 0.0 if model_max == 0 else round(model_score / float(model_max), 6),
            "reasoning_score": model_reasoning_score,
            "reasoning_max_score": model_reasoning_max,
            "fix_score": model_fix_score,
            "fix_max_score": model_fix_max,
            "reasoning_weight": reasoning_weight,
            "fix_weight": fix_weight,
        },
        "issues": rows,
    }
    return validate_answer_key_score_report(summary)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a ReviewRun artifact directory against a fixture answer key.")
    parser.add_argument("--run-dir", required=True, help="ReviewRun artifact directory.")
    parser.add_argument(
        "--answer-key",
        default="scripts/reviewrun/30page_fixture_v1.json",
        help="Answer key JSON file.",
    )
    parser.add_argument(
        "--out",
        default="benchmarks/results/reviewrun/reviewrun_answer_key_score.json",
        help="Where to write the score report JSON.",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    answer_key = Path(args.answer_key).resolve()
    out_path = Path(args.out).resolve()
    if not run_dir.is_dir():
        raise SystemExit(f"--run-dir does not exist: {run_dir}")
    if not answer_key.is_file():
        raise SystemExit(f"--answer-key not found: {answer_key}")

    report = score_answer_key(run_dir=run_dir, answer_key_path=answer_key)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
