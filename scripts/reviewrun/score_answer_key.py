from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Dict, List


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


def _contains_theme(corpus: str, theme: str) -> bool:
    norm = _normalize_text(theme)
    if not norm:
        return False
    token_len = max(5, min(16, len(norm.split())))
    needle = " ".join(norm.split()[:token_len])
    return needle in _normalize_text(corpus)


def score_answer_key(
    *,
    run_dir: Path,
    answer_key_path: Path,
) -> Dict[str, Any]:
    snapshot = _load_json(run_dir / "snapshot.json")
    deterministic = _load_json(run_dir / "deterministic_decision.json")
    model_path = run_dir / "model_assisted_critique.json"
    model = _load_json(model_path) if model_path.is_file() else None
    key = _load_json(answer_key_path)

    changed_paths = [str(item.get("path") or "") for item in list(snapshot.get("changed_files") or [])]
    diff_unified = str(snapshot.get("diff_unified") or "")
    finding_text = _json_blob(deterministic.get("findings") or [])
    model_text = _json_blob(model) if isinstance(model, dict) else ""

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
            if issue_id and issue_id in model_text:
                model_hit = True
            elif compiled:
                model_hit = _matches_any(compiled, model_text)
            for bullet in list(issue.get("expected_reasoning") or []):
                if _contains_theme(model_text, str(bullet or "")):
                    reason_hits += 1
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
        "fixture_id": str(key.get("fixture_id") or ""),
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
        },
        "issues": rows,
    }
    return summary


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
        default="benchmarks/results/reviewrun_answer_key_score.json",
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
