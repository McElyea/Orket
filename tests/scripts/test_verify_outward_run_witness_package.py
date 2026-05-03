from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.outward_run_witness_contract import (
    COMPARE_SCOPE_DENIED,
    COMPARE_SCOPE_POLICY_REJECTED,
    REPORT_SCHEMA_VERSION,
)
from scripts.proof.verify_outward_run_witness_package import main, verify_package
from tests.scripts.test_outward_run_invariant_checker import (
    _valid_denial_package,
    _valid_package,
    _valid_policy_rejected_package,
)
from tests.scripts.test_outward_run_witness_package import _minimal_package


def _without_diff_ledger(payload: dict[str, object]) -> dict[str, object]:
    clean = dict(payload)
    clean.pop("diff_ledger", None)
    return clean


def test_verifier_rejects_missing_package_with_stable_output(tmp_path: Path) -> None:
    """Layer: contract. Verifies proof execution without --package writes a stable rejected report."""
    output = tmp_path / "report.json"

    exit_code = main(["--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["result"] == "rejected"
    assert report["missing_evidence"] == ["package_required_for_proof"]


def test_verifier_writes_outward_run_witness_report_v1(tmp_path: Path) -> None:
    """Layer: contract. Verifies the verifier command persists the report schema through the diff-ledger writer."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    output = tmp_path / "report.json"

    exit_code = main(["--package", str(package_root), "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["result"] == "rejected"
    assert "run_authority_missing" in report["missing_evidence"]
    assert isinstance(report["diff_ledger"], list)


def test_verifier_payload_is_deterministic_for_identical_package_bytes(tmp_path: Path) -> None:
    """Layer: unit. Verifies identical package bytes produce identical proof payloads before diff-ledger metadata."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")

    first = verify_package(package_root)
    second = verify_package(package_root)

    assert _without_diff_ledger(first) == _without_diff_ledger(second)


def test_verifier_accepts_valid_single_turn_package(tmp_path: Path) -> None:
    """Layer: contract. Verifies the package verifier accepts a complete approved-path package."""
    package_root = _valid_package(tmp_path / "outward_run_witness_package.v1")

    report = verify_package(package_root)

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["result"] == "accepted"
    assert report["claim_tier_assigned"] == "outward_lab_only"
    assert report["missing_evidence"] == []


def test_verifier_accepts_valid_denial_package(tmp_path: Path) -> None:
    """Layer: unit. Verifies the package verifier accepts a complete denial-path package."""
    package_root = _valid_denial_package(tmp_path / "outward_run_witness_package.v1")

    report = verify_package(package_root, scope=COMPARE_SCOPE_DENIED)

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["result"] == "accepted"
    assert report["claim_tier_assigned"] == "outward_lab_only"
    assert report["missing_evidence"] == []


def test_verifier_accepts_valid_policy_rejected_package(tmp_path: Path) -> None:
    """Layer: unit. Verifies the package verifier accepts a complete policy-rejection package."""
    package_root = _valid_policy_rejected_package(tmp_path / "outward_run_witness_package.v1")

    report = verify_package(package_root, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["result"] == "accepted"
    assert report["claim_tier_assigned"] == "outward_lab_only"
    assert report["missing_evidence"] == []
