from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import EvalResult, FailingCase


def parse_normalized_report(report_json_path: Path, report_md_path: Path) -> EvalResult:
    payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    cases: list[FailingCase] = []
    for item in payload.get("failing_cases", []):
        if not isinstance(item, dict):
            continue
        case_id = str(item.get("case_id") or "").strip()
        if not case_id:
            continue
        severity = float(item.get("severity", 1.0))
        hard = bool(item.get("hard", False))
        cases.append(FailingCase(case_id=case_id, severity=severity, hard=hard))
    cases.sort(key=lambda row: (row.case_id, -row.severity, row.hard))
    return EvalResult(
        score=float(payload.get("score", 0.0)),
        hard_fail_count=int(payload.get("hard_fail_count", 0)),
        soft_fail_count=int(payload.get("soft_fail_count", 0)),
        failing_cases=tuple(cases),
        report_json_path=report_json_path,
        report_md_path=report_md_path,
    )


def normalize_external_payload(payload: dict[str, Any]) -> dict[str, Any]:
    score = float(payload.get("score", 0.0))
    hard_fail_count = int(payload.get("hard_fail_count", 0))
    soft_fail_count = int(payload.get("soft_fail_count", 0))
    rows = payload.get("failing_cases", [])
    normalized: list[dict[str, Any]] = []
    if isinstance(rows, list):
        for item in rows:
            if not isinstance(item, dict):
                continue
            case_id = str(item.get("case_id") or "").strip()
            if not case_id:
                continue
            normalized.append(
                {
                    "case_id": case_id,
                    "severity": float(item.get("severity", 1.0)),
                    "hard": bool(item.get("hard", False)),
                }
            )
    normalized.sort(key=lambda row: (str(row["case_id"]), -float(row["severity"]), bool(row["hard"])))
    return {
        "score": score,
        "hard_fail_count": hard_fail_count,
        "soft_fail_count": soft_fail_count,
        "failing_cases": normalized,
    }

