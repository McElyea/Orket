from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROMPT_PROFILE = "baseline_v2"
DEFAULT_REVIEW_METHOD = "single_pass"
S04_CLAIM_TIER = "non_deterministic_lab_only"
S04_COMPARE_SCOPE = "workload_s04_fixture_v1"
S04_OPERATOR_SURFACE = "workload_answer_key_scoring_verdict_v1"
S04_AUTHORITATIVE_TRUTH_SURFACE = "deterministic_fingerprint_plus_answer_key_scoring_v1"
S04_MODEL_ASSISTANCE_SURFACE = "model_assisted_review_critique_v0"

_PROMPT_PROFILES: dict[str, dict[str, Any]] = {
    "baseline_v2": {
        "max_high_risk_issues": 5,
        "system_focus": "Focus on concrete security, correctness, and verification risks present in the file.",
        "user_focus": [
            "Report only issues supported by the file contents.",
            "Prefer high-signal findings over nits.",
            "Sort high-risk issues from highest to lowest risk.",
            "Return at most 5 high-risk issues.",
            "Call out missing tests when they matter.",
            "Do not assume repo context that is not shown.",
        ],
    },
    "verification_focus_v1": {
        "max_high_risk_issues": 5,
        "system_focus": (
            "Focus on security, persistence truth, logging exposure, fake verification, and correctness drift "
            "that would make an audit or operator trust the wrong result."
        ),
        "user_focus": [
            "Inspect unsafe parsing or execution of request data.",
            "Inspect payload logging, accidental disclosure, or debug leakage.",
            "Inspect fake verification or integrity checks whose result is ignored or trivial to bypass.",
            "Inspect exception swallowing or success being reported after a failed write.",
            "Inspect numeric validation mistakes that can corrupt totals or percentages.",
            "Return at most 5 high-risk issues sorted by risk.",
        ],
    },
}

_GUARD_CHECKLIST = [
    "unsafe parsing or execution of request data",
    "payload logging or accidental disclosure",
    "fake verification or trivial signature bypass",
    "persistence failure hidden behind success",
    "numeric validation drift affecting totals",
]


class ModelRiskIssueModel(BaseModel):
    why: str
    where: str
    impact: str
    confidence: float
    suggested_fix: str


class ReviewContract(BaseModel):
    summary: list[str] = Field(default_factory=list)
    high_risk_issues: list[ModelRiskIssueModel] = Field(default_factory=list)
    missing_tests: list[str] = Field(default_factory=list)
    questions_for_author: list[str] = Field(default_factory=list)
    nits: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)


ReviewContract.model_rebuild()


def sha256_text(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def sha256_json(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(load_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def artifact_inventory(artifact_dir: Path) -> list[str]:
    return [path.relative_to(artifact_dir).as_posix() for path in sorted(artifact_dir.rglob("*")) if path.is_file()]


def prompt_profile_names() -> list[str]:
    return sorted(_PROMPT_PROFILES)


def resolve_prompt_profile(name: str) -> dict[str, Any]:
    profile = _PROMPT_PROFILES.get(str(name or "").strip())
    if profile is None:
        raise ValueError(f"unknown_prompt_profile:{name}")
    return profile


def build_review_messages(*, fixture_path: Path, source_text: str, prompt_profile: str) -> list[dict[str, str]]:
    profile = resolve_prompt_profile(prompt_profile)
    max_issues = int(profile.get("max_high_risk_issues") or 5)
    system_prompt = (
        "You are reviewing a single Python file. "
        "Return exactly one JSON object with keys summary, high_risk_issues, missing_tests, "
        "questions_for_author, nits, refs. "
        "summary must be an array of 1 to 3 short strings. "
        f"high_risk_issues must be an array of at most {max_issues} objects. "
        "Each high_risk_issues item must include why, where, impact, confidence, suggested_fix. "
        "confidence must be a number between 0.0 and 1.0. "
        "missing_tests must be an array of at most 3 short strings. "
        "questions_for_author must be an array of at most 3 short strings. "
        "Use refs as an empty array unless a short code token is necessary. "
        f"{str(profile.get('system_focus') or '').strip()} "
        "Use short where values such as a function name or one code fragment, not full multi-line excerpts. "
        "Do not use markdown fences."
    )
    user_lines = [
        "Review this file as if it were a real code review.",
        "Requirements:",
        *[f"- {line}" for line in list(profile.get("user_focus") or [])],
        "",
        f"File path: {fixture_path.as_posix()}",
        "File contents:",
        source_text,
    ]
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def build_guard_messages(
    *,
    fixture_path: Path,
    source_text: str,
    draft_response_text: str,
    prompt_profile: str,
) -> list[dict[str, str]]:
    profile = resolve_prompt_profile(prompt_profile)
    max_issues = int(profile.get("max_high_risk_issues") or 5)
    checklist = "\n".join(f"- {item}" for item in _GUARD_CHECKLIST)
    system_prompt = (
        "You are validating and revising a draft code review for a single Python file. "
        "Return exactly one JSON object with keys summary, high_risk_issues, missing_tests, "
        "questions_for_author, nits, refs. "
        f"Keep at most {max_issues} high_risk_issues sorted from highest to lowest risk. "
        "Keep only findings supported by the file. "
        "Do not use markdown fences."
    )
    user_prompt = (
        "Revise the draft review after checking the file against this coverage checklist:\n"
        f"{checklist}\n\n"
        f"File path: {fixture_path.as_posix()}\n"
        "File contents:\n"
        f"{source_text}\n\n"
        f"Draft review:\n{draft_response_text}\n\n"
        "If the draft missed a supported high-risk issue, add it. If a draft claim is unsupported, remove it."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_object(text: str) -> dict[str, Any] | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    possible_payloads = [candidate]
    if "```" in candidate:
        parts = candidate.split("```")
        possible_payloads.extend(part.strip() for part in parts if part.strip())
    brace_start = candidate.find("{")
    brace_end = candidate.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        possible_payloads.append(candidate[brace_start : brace_end + 1].strip())

    for raw in possible_payloads:
        normalized = raw
        if normalized.startswith("json\n") or normalized.startswith("JSON\n"):
            normalized = normalized[5:].strip()
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def empty_review_payload(advisory_errors: list[str]) -> dict[str, Any]:
    return {
        "summary": [],
        "high_risk_issues": [],
        "missing_tests": [],
        "questions_for_author": [],
        "nits": [],
        "refs": [],
        "advisory_errors": list(advisory_errors),
    }


def validated_review_payload(text: str) -> tuple[dict[str, Any], bool, bool, list[str]]:
    advisory_errors: list[str] = []
    extracted = extract_json_object(text)
    if extracted is None:
        advisory_errors.append("response_json_not_found")
        return empty_review_payload(advisory_errors), False, False, advisory_errors
    try:
        validated = ReviewContract.model_validate(extracted)
    except ValidationError as exc:
        advisory_errors.append(f"contract_validation_error:{exc}")
        payload = empty_review_payload(advisory_errors)
        payload["raw_extracted_json"] = extracted
        return payload, True, False, advisory_errors
    payload = validated.model_dump()
    payload["advisory_errors"] = list(advisory_errors)
    return payload, True, True, advisory_errors


def build_snapshot_payload(*, fixture_path: Path, source_text: str) -> dict[str, Any]:
    return {
        "snapshot_digest": sha256_text(source_text),
        "changed_files": [{"path": fixture_path.as_posix()}],
        "diff_unified": source_text,
    }


def _compile_patterns(raw_patterns: list[Any]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for item in raw_patterns:
        text = str(item or "").strip()
        if not text:
            continue
        try:
            compiled.append(re.compile(text, re.IGNORECASE | re.MULTILINE))
        except re.error:
            compiled.append(re.compile(re.escape(text), re.IGNORECASE | re.MULTILINE))
    return compiled


def build_deterministic_payload(*, source_text: str, answer_key: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    executed_checks: list[dict[str, Any]] = []
    for issue in list(answer_key.get("issues") or []):
        if not isinstance(issue, dict):
            continue
        issue_id = str(issue.get("issue_id") or "").strip()
        compiled = _compile_patterns(list(issue.get("fingerprints") or []))
        matched = [pattern.pattern for pattern in compiled if pattern.search(source_text)]
        executed_checks.append(
            {
                "issue_id": issue_id,
                "matched": bool(matched),
                "matched_fingerprints": matched,
                "rule_version": "s04_static_fingerprint_v1",
            }
        )
        if not matched:
            continue
        findings.append(
            {
                "issue_id": issue_id,
                "message": str(issue.get("why") or issue_id),
                "severity": str(issue.get("severity") or ""),
                "details": {
                    "tags": [issue_id],
                    "matched_fingerprints": matched,
                    "category": str(issue.get("category") or ""),
                    "must_catch": bool(issue.get("must_catch") or False),
                },
            }
        )
    return {
        "policy_digest": sha256_text("workloads.s04_code_review_probe.static_patterns_v1"),
        "findings": findings,
        "executed_checks": executed_checks,
        "deterministic_lane_version": "s04_static_fingerprint_v1",
    }


def build_governed_claim_payload(
    *,
    provider: str,
    model: str,
    prompt_profile: str,
    review_method: str,
    temperature: float,
    seed: int,
    timeout: int,
    fixture_path: Path,
    answer_key_path: Path,
) -> dict[str, str]:
    policy_payload = {
        "workload_schema_version": "workloads.s04_code_review_probe.v2",
        "score_policy": "reviewrun.answer_key_scoring.v2",
        "deterministic_lane_version": "s04_static_fingerprint_v1",
        "prompt_profile": str(prompt_profile),
        "review_method": str(review_method),
    }
    control_bundle = {
        "provider": str(provider),
        "model": str(model),
        "temperature": float(temperature),
        "seed": int(seed),
        "timeout": int(timeout),
        "fixture_path": fixture_path.as_posix(),
        "answer_key_path": answer_key_path.as_posix(),
    }
    return {
        "claim_tier": S04_CLAIM_TIER,
        "compare_scope": S04_COMPARE_SCOPE,
        "operator_surface": S04_OPERATOR_SURFACE,
        "policy_digest": sha256_json(policy_payload),
        "control_bundle_hash": sha256_json(control_bundle),
        "authoritative_truth_surface": S04_AUTHORITATIVE_TRUTH_SURFACE,
        "model_assistance_surface": S04_MODEL_ASSISTANCE_SURFACE,
    }


def usage_responses(*, initial_response: Any, final_response: Any, review_method: str) -> list[Any]:
    responses = [initial_response]
    if str(review_method) == "self_check" and final_response is not None and final_response is not initial_response:
        responses.append(final_response)
    return [response for response in responses if response is not None]


def usage_payload(responses: list[Any]) -> dict[str, Any]:
    total_input = sum(int((response.raw or {}).get("input_tokens") or 0) for response in responses)
    total_output = sum(int((response.raw or {}).get("output_tokens") or 0) for response in responses)
    total_latency = sum(int((response.raw or {}).get("latency_ms") or 0) for response in responses)
    return {
        "latency_ms": total_latency,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "passes": [
            {
                "latency_ms": int((response.raw or {}).get("latency_ms") or 0),
                "input_tokens": int((response.raw or {}).get("input_tokens") or 0),
                "output_tokens": int((response.raw or {}).get("output_tokens") or 0),
            }
            for response in responses
        ],
    }
