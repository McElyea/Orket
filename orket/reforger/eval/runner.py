from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.reforger.eval.base import EvalHarness, EvalResult, ModelAdapter
from orket.reforger.eval.parsers import parse_normalized_report


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
    # Lock ordering by case_id for deterministic evaluation.
    rows.sort(key=lambda row: str(row.get("case_id", "")))
    return rows


def _load_pack_text(pack_path: Path) -> str:
    chunks: list[str] = []
    for name in ("system.txt", "system.md", "developer.txt", "constraints.yaml"):
        target = pack_path / name
        if target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def pack_digest(pack_path: Path) -> str:
    payload: list[bytes] = []
    files = sorted(item for item in pack_path.rglob("*") if item.is_file())
    for file_path in files:
        rel = str(file_path.relative_to(pack_path)).replace("\\", "/")
        payload.append(rel.encode("utf-8"))
        payload.append(b"\n")
        payload.append(hashlib.sha256(file_path.read_bytes()).hexdigest().encode("utf-8"))
        payload.append(b"\n")
    return hashlib.sha256(b"".join(payload)).hexdigest()


class HashStubModelAdapter(ModelAdapter):
    def generate(
        self,
        *,
        model_id: str,
        mode_id: str,
        case_id: str,
        prompt: str,
        pack_digest: str,
        pack_path: Path,
    ) -> str:
        del pack_path
        key = f"{model_id}|{mode_id}|{case_id}|{prompt}|{pack_digest}"
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
        if bucket % 11 == 0:
            return "REFUSE\nrefusal_reason:insufficient_truth"
        if bucket % 7 == 0:
            return "NO"
        return "YES"


@dataclass(frozen=True)
class FakeModelFixture:
    outputs: dict[str, str]

    @staticmethod
    def from_path(path: Path) -> "FakeModelFixture":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Fake model fixture must be an object: {path}")
        rows: dict[str, str] = {}
        for key, value in payload.items():
            if isinstance(key, str) and isinstance(value, str):
                rows[key] = value
        return FakeModelFixture(outputs=rows)


class FakeModelAdapter(ModelAdapter):
    """Deterministic canned model for evaluator regression/golden tests."""

    def __init__(self, fixture: FakeModelFixture) -> None:
        self.fixture = fixture

    def generate(
        self,
        *,
        model_id: str,
        mode_id: str,
        case_id: str,
        prompt: str,
        pack_digest: str,
        pack_path: Path,
    ) -> str:
        del model_id, prompt, pack_path
        for key in (
            f"{mode_id}:{case_id}:{pack_digest}",
            f"{mode_id}:{case_id}",
            case_id,
        ):
            if key in self.fixture.outputs:
                return self.fixture.outputs[key]
        return "REFUSE\nrefusal_reason:fake_default"


def _parse_int_suffix(value: str, prefix: str) -> int | None:
    if not value.startswith(prefix):
        return None
    raw = value[len(prefix) :].strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _check_rule(rule: str, *, output: str, pack_text: str) -> bool:
    if rule.startswith("must_include:"):
        needle = rule.split(":", 1)[1].strip()
        return bool(needle) and needle in pack_text
    if rule.startswith("output_must_include:"):
        needle = rule.split(":", 1)[1].strip()
        return bool(needle) and needle in output
    if rule.startswith("output_must_not_include:"):
        needle = rule.split(":", 1)[1].strip()
        return (not needle) or (needle not in output)
    if rule.startswith("output_must_match:"):
        pattern = rule.split(":", 1)[1].strip()
        if not pattern:
            return False
        return re.search(pattern, output, flags=re.MULTILINE) is not None
    if rule.startswith("output_exactly_one_of:"):
        raw = rule.split(":", 1)[1].strip()
        options = [item.strip() for item in raw.split("|") if item.strip()]
        if not options:
            return False
        exact = [item for item in options if output.strip() == item]
        return len(exact) == 1
    if rule.startswith("forbidden_pattern:"):
        token = rule.split(":", 1)[1].strip()
        return (not token) or (token not in output)
    if rule.startswith("must_refuse_if_unknown"):
        return ("refusal_reason:" in output) or output.strip().upper().startswith("REFUSE")
    return True


def _soft_score(rule: str, *, output: str, pack_text: str) -> float:
    if rule.startswith("prefer_include:"):
        needle = rule.split(":", 1)[1].strip()
        return 1.0 if needle and needle in pack_text else 0.0
    if rule.startswith("output_prefer_include:"):
        needle = rule.split(":", 1)[1].strip()
        return 1.0 if needle and needle in output else 0.0
    max_len = _parse_int_suffix(rule, "output_length_max:")
    if max_len is not None:
        return 1.0 if len(output) <= max_len else 0.0
    min_len = _parse_int_suffix(rule, "output_length_min:")
    if min_len is not None:
        return 1.0 if len(output) >= min_len else 0.0
    return 1.0


class AdapterEvalHarness(EvalHarness):
    def __init__(self, adapter: ModelAdapter) -> None:
        self.adapter = adapter

    def run(
        self,
        *,
        model_id: str,
        mode_id: str,
        pack_path: Path,
        suite_path: Path,
        out_dir: Path,
    ) -> EvalResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        cases = _read_cases(suite_path)
        pack_text = _load_pack_text(pack_path)
        digest = pack_digest(pack_path)

        failing_cases: list[dict[str, object]] = []
        per_case: list[dict[str, object]] = []
        score_sum = 0.0
        hard_fail_count = 0
        soft_fail_count = 0
        refusal_count = 0

        for case in cases:
            case_id = str(case.get("case_id") or "").strip()
            prompt = str(case.get("prompt") or "")
            if not case_id:
                continue
            expectations = case.get("expectations") if isinstance(case.get("expectations"), dict) else {}
            hard_rules = expectations.get("hard") if isinstance(expectations, dict) else []
            soft_rules = expectations.get("soft") if isinstance(expectations, dict) else []
            hard_list = [item for item in (hard_rules if isinstance(hard_rules, list) else []) if isinstance(item, str)]
            soft_list = [item for item in (soft_rules if isinstance(soft_rules, list) else []) if isinstance(item, str)]

            output = self.adapter.generate(
                model_id=model_id,
                mode_id=mode_id,
                case_id=case_id,
                prompt=prompt,
                pack_digest=digest,
                pack_path=pack_path,
            )
            if "refusal_reason:" in output:
                refusal_count += 1

            hard_fail = any(not _check_rule(rule, output=output, pack_text=pack_text) for rule in hard_list)
            soft_rule_scores = [_soft_score(rule, output=output, pack_text=pack_text) for rule in soft_list]
            soft_case_score = sum(soft_rule_scores) / len(soft_rule_scores) if soft_rule_scores else 1.0

            if hard_fail:
                hard_fail_count += 1
                case_score = 0.0
                failing_cases.append({"case_id": case_id, "severity": 1.0, "hard": True})
            else:
                case_score = soft_case_score
                if soft_case_score < 1.0:
                    soft_fail_count += 1
                    failing_cases.append({"case_id": case_id, "severity": round(1.0 - soft_case_score, 3), "hard": False})
            score_sum += case_score

            per_case.append(
                {
                    "case_id": case_id,
                    "hard_fail": hard_fail,
                    "soft_score": round(soft_case_score, 6),
                    "score": round(case_score, 6),
                    "output": output,
                }
            )

        failing_cases.sort(key=lambda row: (str(row["case_id"]), -float(row["severity"]), bool(row["hard"])))
        per_case.sort(key=lambda row: str(row["case_id"]))
        case_count = len(per_case)
        total_score = (score_sum / case_count) if case_count else 1.0
        payload = {
            "score": round(total_score, 6),
            "hard_fail_count": hard_fail_count,
            "soft_fail_count": soft_fail_count,
            "failing_cases": failing_cases,
            "case_count": case_count,
            "refusal_count": refusal_count,
            "per_case": per_case,
        }
        report_json_path = out_dir / "report.json"
        report_md_path = out_dir / "report.md"
        report_json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        report_md_path.write_text(
            "\n".join(
                [
                    "# Evaluation Report",
                    "",
                    f"- score: {payload['score']}",
                    f"- hard_fail_count: {hard_fail_count}",
                    f"- soft_fail_count: {soft_fail_count}",
                    f"- refusal_count: {refusal_count}",
                    f"- case_count: {case_count}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return parse_normalized_report(report_json_path, report_md_path)


class StubEvalHarness(AdapterEvalHarness):
    def __init__(self) -> None:
        super().__init__(adapter=HashStubModelAdapter())

