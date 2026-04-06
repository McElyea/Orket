# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.reviewrun.check_1000_consistency import (
    REPORT_CONTRACT_VERSION,
    evaluate_consistency_report,
    main,
)


def _valid_report_payload() -> dict[str, object]:
    strict_signature = {
        "snapshot_digest": "sha256:abc",
        "policy_digest": "sha256:def",
        "deterministic_lane_version": "deterministic_v0",
        "decision": "reject",
        "findings": [
            {
                "code": "PATTERN_MATCHED",
                "severity": "high",
                "message": "Forbidden pattern matched: debug",
                "path": "app/config.py",
                "span": {"start": 1, "end": 1},
                "details": {"pattern": "debug"},
            }
        ],
        "executed_checks": ["deterministic"],
        "truncation": {"diff_truncated": False},
    }
    return {
        "ok": True,
        "contract_version": REPORT_CONTRACT_VERSION,
        "consistency": {
            "runs_requested": 3,
            "runs_checked": 3,
            "baseline_run_id": "run-baseline",
            "baseline_signature": dict(strict_signature),
            "mismatch": None,
        },
        "default_run": {
            "run_id": "run-default",
            "artifact_dir": "default",
            "signature": {**dict(strict_signature), "decision": "accept", "findings": []},
        },
        "strict_run": {
            "run_id": "run-strict",
            "artifact_dir": "strict",
            "signature": dict(strict_signature),
            "strict_policy": {},
        },
        "strict_replay": {
            "run_id": "run-strict-replay",
            "artifact_dir": "strict-replay",
            "signature": dict(strict_signature),
            "parity_with_strict": True,
        },
        "truncation_check": {
            "ok": True,
            "diff_truncated": False,
            "digests_differ": False,
        },
        "scenario": "constants_flags",
    }


def _valid_truncation_report_payload() -> dict[str, object]:
    report = _valid_report_payload()
    report["scenario"] = "truncation_bounds"
    report["truncation_check"] = {
        "ok": True,
        "diff_truncated": True,
        "digests_differ": True,
        "unbounded_snapshot_digest": "sha256:unbounded",
        "truncated_snapshot_digest": "sha256:truncated",
        "diff_bytes_original": 1000,
        "diff_bytes_kept": 300,
    }
    return report


# Layer: contract
def test_evaluate_consistency_report_accepts_valid_payload(tmp_path: Path) -> None:
    payload = evaluate_consistency_report(
        payload=_valid_report_payload(),
        report_path=tmp_path / "report.json",
        expected_runs=3,
    )

    assert payload["ok"] is True
    assert payload["issues"] == []
    assert payload["summary"]["runs_checked"] == 3


# Layer: contract
def test_evaluate_consistency_report_rejects_contract_version_drift(tmp_path: Path) -> None:
    report = _valid_report_payload()
    report["contract_version"] = "drifted"

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_contract_version_invalid" in payload["issues"]


# Layer: contract
def test_evaluate_consistency_report_rejects_missing_default_run_id(tmp_path: Path) -> None:
    report = _valid_report_payload()
    report["default_run"] = {
        "run_id": "",
        "artifact_dir": "default",
        "signature": {
            **dict(report["default_run"]["signature"]),  # type: ignore[index]
        },
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_default_run_id_required" in payload["issues"]


# Layer: contract
def test_evaluate_consistency_report_rejects_missing_baseline_run_id(tmp_path: Path) -> None:
    report = _valid_report_payload()
    report["consistency"] = {
        **dict(report["consistency"]),
        "baseline_run_id": "",
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_baseline_run_id_required" in payload["issues"]


# Layer: contract
def test_evaluate_consistency_report_allows_failed_outcome_when_success_not_required(tmp_path: Path) -> None:
    report = _valid_report_payload()
    report["ok"] = False
    report["consistency"] = {
        **dict(report["consistency"]),
        "mismatch": {"iteration": 2},
    }
    report["strict_replay"] = {
        **dict(report["strict_replay"]),
        "parity_with_strict": False,
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
        require_success=False,
    )

    assert payload["ok"] is True
    assert payload["issues"] == []


# Layer: contract
def test_evaluate_consistency_report_rejects_truncation_check_contract_drift_when_success_not_required(
    tmp_path: Path,
) -> None:
    report = _valid_truncation_report_payload()
    report["truncation_check"] = {
        **dict(report["truncation_check"]),  # type: ignore[arg-type]
        "ok": "yes",
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
        require_success=False,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_truncation_check_ok_invalid" in payload["issues"]


# Layer: integration
def test_evaluate_consistency_report_rejects_default_signature_contract_drift(tmp_path: Path) -> None:
    report = _valid_report_payload()
    report["default_run"] = {
        **dict(report["default_run"]),  # type: ignore[arg-type]
        "signature": {
            **dict(report["default_run"]["signature"]),  # type: ignore[index]
            "executed_checks": "",
        },
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_default_signature_executed_checks_invalid" in payload["issues"]


# Layer: contract
def test_evaluate_consistency_report_rejects_signature_finding_row_contract_drift(
    tmp_path: Path,
) -> None:
    report = _valid_report_payload()
    report["strict_run"] = {
        **dict(report["strict_run"]),  # type: ignore[arg-type]
        "signature": {
            **dict(report["strict_run"]["signature"]),  # type: ignore[index]
            "findings": [
                {
                    "code": "PATTERN_MATCHED",
                    "severity": "",
                    "message": "Forbidden pattern matched: debug",
                    "path": "app/config.py",
                    "span": {"start": 1, "end": 1},
                    "details": {"pattern": "debug"},
                }
            ],
        },
    }

    payload = evaluate_consistency_report(
        payload=report,
        report_path=tmp_path / "report.json",
        expected_runs=3,
        require_success=False,
    )

    assert payload["ok"] is False
    assert "reviewrun_consistency_strict_signature_findings_severity_invalid" in payload["issues"]


# Layer: integration
def test_main_returns_failure_for_missing_default_run_id(tmp_path: Path) -> None:
    report_path = tmp_path / "reviewrun_consistency.json"
    report = _valid_report_payload()
    report["default_run"] = {
        "run_id": "",
        "artifact_dir": "default",
        "signature": {
            **dict(report["default_run"]["signature"]),  # type: ignore[index]
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")

    exit_code = main(["--report", str(report_path), "--expected-runs", "3"])

    assert exit_code == 1


# Layer: integration
def test_main_returns_failure_for_invalid_signature_finding_row_contract(tmp_path: Path) -> None:
    report_path = tmp_path / "reviewrun_consistency.json"
    report = _valid_report_payload()
    report["strict_replay"] = {
        **dict(report["strict_replay"]),  # type: ignore[arg-type]
        "signature": {
            **dict(report["strict_replay"]["signature"]),  # type: ignore[index]
            "findings": [
                {
                    "code": "PATTERN_MATCHED",
                    "severity": "high",
                    "message": "",
                    "path": "app/config.py",
                    "span": {"start": 1, "end": 1},
                    "details": {"pattern": "debug"},
                }
            ],
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")

    exit_code = main(["--report", str(report_path), "--expected-runs", "3"])

    assert exit_code == 1


# Layer: integration
def test_main_returns_failure_for_invalid_truncation_check_contract(tmp_path: Path) -> None:
    report_path = tmp_path / "reviewrun_consistency.json"
    report = _valid_truncation_report_payload()
    report["truncation_check"] = {
        **dict(report["truncation_check"]),  # type: ignore[arg-type]
        "unbounded_snapshot_digest": "",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")

    exit_code = main(["--report", str(report_path), "--expected-runs", "3"])

    assert exit_code == 1
