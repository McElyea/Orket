from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from orket.application.review.control_plane_projection import validate_review_required_identifier


REPORT_CONTRACT_VERSION = "reviewrun_consistency_check_v1"


def _append_required_run_id_issue(issues: list[str], value: Any, *, error: str) -> None:
    try:
        validate_review_required_identifier(value, error=error)
    except ValueError as exc:
        issues.append(str(exc))


def _append_required_sha256_issue(issues: list[str], value: Any, *, error: str) -> None:
    if not str(value or "").startswith("sha256:"):
        issues.append(error)


def _append_required_non_empty_text_issue(issues: list[str], value: Any, *, error: str) -> None:
    if not str(value or "").strip():
        issues.append(error)


def _append_required_string_list_issue(issues: list[str], value: Any, *, error: str) -> None:
    if not isinstance(value, list):
        issues.append(error)
        return
    if any(not str(item or "").strip() for item in value):
        issues.append(error)


def _append_required_boolean_issue(issues: list[str], value: Any, *, error: str) -> None:
    if not isinstance(value, bool):
        issues.append(error)


def _append_required_non_negative_int_issue(issues: list[str], value: Any, *, error: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        issues.append(error)


def _append_required_finding_rows_issue(
    issues: list[str],
    value: Any,
    *,
    error_prefix: str,
) -> None:
    if not isinstance(value, list):
        issues.append(f"{error_prefix}_invalid")
        return
    for row in value:
        if not isinstance(row, dict):
            issues.append(f"{error_prefix}_row_invalid")
            continue
        _append_required_non_empty_text_issue(
            issues,
            row.get("code"),
            error=f"{error_prefix}_code_invalid",
        )
        _append_required_non_empty_text_issue(
            issues,
            row.get("severity"),
            error=f"{error_prefix}_severity_invalid",
        )
        _append_required_non_empty_text_issue(
            issues,
            row.get("message"),
            error=f"{error_prefix}_message_invalid",
        )
        if not isinstance(row.get("path"), str):
            issues.append(f"{error_prefix}_path_invalid")
        span = row.get("span")
        if not isinstance(span, dict):
            issues.append(f"{error_prefix}_span_invalid")
        else:
            if "start" in span:
                _append_required_non_negative_int_issue(
                    issues,
                    span.get("start"),
                    error=f"{error_prefix}_span_start_invalid",
                )
            if "end" in span:
                _append_required_non_negative_int_issue(
                    issues,
                    span.get("end"),
                    error=f"{error_prefix}_span_end_invalid",
                )
        if not isinstance(row.get("details"), dict):
            issues.append(f"{error_prefix}_details_invalid")


def _append_required_truncation_issue(issues: list[str], value: Any, *, error_prefix: str) -> None:
    if not isinstance(value, dict):
        issues.append(f"{error_prefix}_invalid")
        return
    if not isinstance(value.get("diff_truncated"), bool):
        issues.append(f"{error_prefix}_diff_truncated_invalid")


def _append_signature_contract_issues(
    issues: list[str],
    value: Any,
    *,
    prefix: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        issues.append(f"{prefix}_invalid")
        return {}

    _append_required_sha256_issue(
        issues,
        value.get("snapshot_digest"),
        error=f"{prefix}_snapshot_digest_invalid",
    )
    _append_required_sha256_issue(
        issues,
        value.get("policy_digest"),
        error=f"{prefix}_policy_digest_invalid",
    )
    _append_required_non_empty_text_issue(
        issues,
        value.get("deterministic_lane_version"),
        error=f"{prefix}_deterministic_lane_version_invalid",
    )
    _append_required_non_empty_text_issue(
        issues,
        value.get("decision"),
        error=f"{prefix}_decision_invalid",
    )
    _append_required_finding_rows_issue(
        issues,
        value.get("findings"),
        error_prefix=f"{prefix}_findings",
    )
    _append_required_string_list_issue(
        issues,
        value.get("executed_checks"),
        error=f"{prefix}_executed_checks_invalid",
    )
    _append_required_truncation_issue(
        issues,
        value.get("truncation"),
        error_prefix=f"{prefix}_truncation",
    )
    return dict(value)


def _append_truncation_check_contract_issues(
    issues: list[str],
    value: Any,
    *,
    prefix: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        issues.append(f"{prefix}_invalid")
        return {}

    _append_required_sha256_issue(
        issues,
        value.get("unbounded_snapshot_digest"),
        error=f"{prefix}_unbounded_snapshot_digest_invalid",
    )
    _append_required_sha256_issue(
        issues,
        value.get("truncated_snapshot_digest"),
        error=f"{prefix}_truncated_snapshot_digest_invalid",
    )
    _append_required_boolean_issue(
        issues,
        value.get("ok"),
        error=f"{prefix}_ok_invalid",
    )
    _append_required_boolean_issue(
        issues,
        value.get("diff_truncated"),
        error=f"{prefix}_diff_truncated_invalid",
    )
    _append_required_boolean_issue(
        issues,
        value.get("digests_differ"),
        error=f"{prefix}_digests_differ_invalid",
    )
    _append_required_non_negative_int_issue(
        issues,
        value.get("diff_bytes_original"),
        error=f"{prefix}_diff_bytes_original_invalid",
    )
    _append_required_non_negative_int_issue(
        issues,
        value.get("diff_bytes_kept"),
        error=f"{prefix}_diff_bytes_kept_invalid",
    )
    return dict(value)


def evaluate_consistency_report(
    *,
    payload: Any,
    report_path: Path,
    expected_runs: int,
    require_success: bool = True,
) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        issues.append("reviewrun_consistency_report_invalid")
        return {
            "ok": False,
            "report": str(report_path),
            "expected_runs": int(expected_runs),
            "issues": issues,
            "summary": {
                "runs_checked": 0,
                "default_decision": "",
                "strict_decision": "",
                "strict_findings_count": 0,
                "strict_replay_parity": False,
                "scenario": "",
            },
        }

    if str(payload.get("contract_version") or "").strip() != REPORT_CONTRACT_VERSION:
        issues.append("reviewrun_consistency_contract_version_invalid")

    if require_success and not bool(payload.get("ok")):
        issues.append("report.ok is false")
    consistency = payload.get("consistency") if isinstance(payload.get("consistency"), dict) else {}
    runs_checked = int(consistency.get("runs_checked") or 0)
    if runs_checked != int(expected_runs):
        issues.append(
            f"runs_checked mismatch: expected={int(expected_runs)} actual={runs_checked}"
        )
    if runs_checked > 0:
        _append_required_run_id_issue(
            issues,
            consistency.get("baseline_run_id"),
            error="reviewrun_consistency_baseline_run_id_required",
        )
    baseline = _append_signature_contract_issues(
        issues,
        consistency.get("baseline_signature"),
        prefix="reviewrun_consistency_baseline_signature",
    )
    if require_success and consistency.get("mismatch") not in (None, {}):
        issues.append("mismatch payload is present")
    default_run = payload.get("default_run") if isinstance(payload.get("default_run"), dict) else {}
    strict_run = payload.get("strict_run") if isinstance(payload.get("strict_run"), dict) else {}
    strict_replay = payload.get("strict_replay") if isinstance(payload.get("strict_replay"), dict) else {}
    _append_required_run_id_issue(
        issues,
        default_run.get("run_id"),
        error="reviewrun_consistency_default_run_id_required",
    )
    _append_required_run_id_issue(
        issues,
        strict_run.get("run_id"),
        error="reviewrun_consistency_strict_run_id_required",
    )
    _append_required_run_id_issue(
        issues,
        strict_replay.get("run_id"),
        error="reviewrun_consistency_strict_replay_run_id_required",
    )
    default_sig = _append_signature_contract_issues(
        issues,
        default_run.get("signature"),
        prefix="reviewrun_consistency_default_signature",
    )
    strict_sig = _append_signature_contract_issues(
        issues,
        strict_run.get("signature"),
        prefix="reviewrun_consistency_strict_signature",
    )
    replay_sig = _append_signature_contract_issues(
        issues,
        strict_replay.get("signature"),
        prefix="reviewrun_consistency_strict_replay_signature",
    )
    if require_success and not bool(strict_replay.get("parity_with_strict")):
        issues.append("strict replay parity failed")
    if require_success and int(len(list(strict_sig.get("findings") or []))) <= 0:
        issues.append("strict run has no findings")
    if not isinstance(strict_run.get("strict_policy"), dict):
        issues.append("strict policy payload missing")
    if not str(default_sig.get("decision") or "").strip():
        issues.append("default decision missing")
    if not str(strict_sig.get("decision") or "").strip():
        issues.append("strict decision missing")
    if require_success and strict_sig != replay_sig:
        issues.append("strict and replay signatures differ")
    scenario = str(payload.get("scenario") or "")
    strict_findings = list(strict_sig.get("findings") or [])
    if scenario in {"auth_insecure", "secrets_sha1"}:
        for finding in strict_findings:
            if str(finding.get("code") or "") != "PATTERN_MATCHED":
                continue
            if not str(finding.get("path") or "").strip():
                issues.append("PATTERN_MATCHED finding missing path")
                break
            span = finding.get("span") if isinstance(finding.get("span"), dict) else {}
            if int(span.get("start") or 0) <= 0:
                issues.append("PATTERN_MATCHED finding missing positive span.start")
                break
    truncation_check = {}
    if scenario == "truncation_bounds":
        truncation_check = _append_truncation_check_contract_issues(
            issues,
            payload.get("truncation_check"),
            prefix="reviewrun_consistency_truncation_check",
        )
    if require_success and scenario == "truncation_bounds":
        if truncation_check.get("ok") is not True:
            issues.append("truncation_check.ok is false")
        if truncation_check.get("diff_truncated") is not True:
            issues.append("truncation_check.diff_truncated is false")
        if truncation_check.get("digests_differ") is not True:
            issues.append("truncation_check.digests_differ is false")

    return {
        "ok": len(issues) == 0,
        "report": str(report_path),
        "expected_runs": int(expected_runs),
        "issues": issues,
        "summary": {
            "runs_checked": runs_checked,
            "default_decision": str(default_sig.get("decision") or ""),
            "strict_decision": str(strict_sig.get("decision") or ""),
            "strict_findings_count": len(list(strict_sig.get("findings") or [])),
            "strict_replay_parity": bool(strict_replay.get("parity_with_strict")),
            "scenario": scenario,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate ReviewRun 1000 consistency report.")
    parser.add_argument(
        "--report",
        type=str,
        default="benchmarks/results/reviewrun/reviewrun_consistency_1000.json",
        help="Path to report generated by run_1000_consistency.py",
    )
    parser.add_argument("--expected-runs", type=int, default=1000, help="Expected number of runs checked.")
    args = parser.parse_args(argv)

    report_path = Path(args.report).resolve()
    if not report_path.is_file():
        print(json.dumps({"ok": False, "error": "report_not_found", "report": str(report_path)}, indent=2))
        return 2

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    result = evaluate_consistency_report(
        payload=payload,
        report_path=report_path,
        expected_runs=int(args.expected_runs),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
