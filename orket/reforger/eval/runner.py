from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .base import EvalHarness, EvalResult
from .parsers import parse_normalized_report


def _read_cases(suite_path: Path) -> list[dict[str, Any]]:
    cases_file = suite_path / "cases.jsonl"
    if not cases_file.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in cases_file.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        payload = json.loads(text)
        if isinstance(payload, dict):
            rows.append(payload)
    rows.sort(key=lambda row: str(row.get("case_id", "")))
    return rows


def _load_pack_text(pack_path: Path) -> str:
    chunks: list[str] = []
    for name in ("system.txt", "system.md", "developer.txt", "constraints.yaml"):
        target = pack_path / name
        if target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _score_case(*, case: dict[str, Any], pack_text: str, pack_hash: str) -> tuple[float, bool, bool]:
    case_id = str(case.get("case_id") or "")
    expectations = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
    hard_checks = expectations.get("hard") if isinstance(expectations, dict) else []
    soft_checks = expectations.get("soft") if isinstance(expectations, dict) else []
    hard_list = hard_checks if isinstance(hard_checks, list) else []
    soft_list = soft_checks if isinstance(soft_checks, list) else []

    base_key = f"{case_id}|{pack_hash}"
    bucket = int(hashlib.sha256(base_key.encode("utf-8")).hexdigest()[:8], 16)
    hard_fail = (bucket % 17) == 0
    soft_fail = (bucket % 5) == 0

    for item in hard_list:
        if not isinstance(item, str):
            continue
        if item.startswith("must_include:"):
            needle = item.split(":", 1)[1].strip()
            if needle and needle not in pack_text:
                hard_fail = True
    for item in soft_list:
        if not isinstance(item, str):
            continue
        if item.startswith("prefer_include:"):
            needle = item.split(":", 1)[1].strip()
            if needle and needle not in pack_text:
                soft_fail = True

    if hard_fail:
        return 0.0, True, soft_fail
    if soft_fail:
        return 0.5, False, True
    return 1.0, False, False


class StubEvalHarness(EvalHarness):
    def run(
        self,
        *,
        model_id: str,
        mode_id: str,
        pack_path: Path,
        suite_path: Path,
        out_dir: Path,
    ) -> EvalResult:
        del model_id, mode_id
        out_dir.mkdir(parents=True, exist_ok=True)
        cases = _read_cases(suite_path)
        pack_text = _load_pack_text(pack_path)
        pack_hash = hashlib.sha256(pack_text.encode("utf-8")).hexdigest()

        scores: list[float] = []
        failing_cases: list[dict[str, object]] = []
        hard_fail_count = 0
        soft_fail_count = 0

        for case in cases:
            case_id = str(case.get("case_id") or "").strip()
            if not case_id:
                continue
            case_score, hard_fail, soft_fail = _score_case(case=case, pack_text=pack_text, pack_hash=pack_hash)
            scores.append(case_score)
            if hard_fail:
                hard_fail_count += 1
                failing_cases.append({"case_id": case_id, "severity": 1.0, "hard": True})
            elif soft_fail:
                soft_fail_count += 1
                failing_cases.append({"case_id": case_id, "severity": 0.5, "hard": False})

        total = len(scores)
        score = (sum(scores) / total) if total else 1.0
        failing_cases.sort(key=lambda row: (str(row["case_id"]), -float(row["severity"]), bool(row["hard"])))

        report_payload = {
            "score": round(float(score), 6),
            "hard_fail_count": hard_fail_count,
            "soft_fail_count": soft_fail_count,
            "failing_cases": failing_cases,
            "case_count": total,
        }

        report_json_path = out_dir / "report.json"
        report_md_path = out_dir / "report.md"
        report_json_path.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")
        report_md_path.write_text(
            "\n".join(
                [
                    "# Evaluation Report",
                    "",
                    f"- score: {report_payload['score']}",
                    f"- hard_fail_count: {hard_fail_count}",
                    f"- soft_fail_count: {soft_fail_count}",
                    f"- case_count: {total}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return parse_normalized_report(report_json_path=report_json_path, report_md_path=report_md_path)

