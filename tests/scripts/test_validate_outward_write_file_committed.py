from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.validate_outward_write_file_committed import main, validate_package_artifact
from tests.scripts.test_outward_run_witness_ledger import _rewrite_manifest
from tests.scripts.test_outward_run_witness_package import _minimal_package


def test_validate_committed_artifact_cli_accepts_valid_package(tmp_path: Path) -> None:
    """Layer: contract. Verifies the committed artifact validator writes rerunnable JSON."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    output = tmp_path / "artifact-report.json"

    exit_code = main(["--package", str(package_root), "--output", str(output)])
    report = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert report["schema_version"] == "outward_write_file_committed_validation.v1"
    assert report["result"] == "accepted"
    assert report["missing_evidence"] == []
    assert isinstance(report["diff_ledger"], list)


def test_validate_committed_artifact_reports_missing_package_bytes(tmp_path: Path) -> None:
    """Layer: contract. Verifies the artifact validator fails closed when package bytes are absent."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "artifacts" / "committed_output").unlink()
    _rewrite_manifest(package_root)

    report = validate_package_artifact(package_root)

    assert report["result"] == "rejected"
    assert report["missing_evidence"] == ["committed_artifact_missing"]


def test_validate_committed_artifact_reports_digest_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies artifact digest drift is reported with a stable code."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "artifacts" / "committed_output").write_bytes(b"changed\n")
    _rewrite_manifest(package_root)

    report = validate_package_artifact(package_root)

    assert report["result"] == "rejected"
    assert report["missing_evidence"] == ["artifact_digest_mismatch"]
