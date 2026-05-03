from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.outward_run_witness_contract import compute_package_digest, file_sha256
from scripts.proof.outward_run_witness_package import load_witness_package
from scripts.proof.outward_run_witness_ledger import verify_committed_artifact, verify_package_ledger
from tests.scripts.test_outward_run_witness_package import _minimal_package


def _rewrite_manifest(package_root: Path) -> None:
    manifest_path = package_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = [
        "outward_witness_bundle.json",
        "ledger_export.json",
        "artifacts/committed_output",
    ]
    manifest["file_digests"] = {
        path: file_sha256(package_root / path) for path in paths if (package_root / path).exists()
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_package_ledger_verifies_full_export_digest_and_chain(tmp_path: Path) -> None:
    """Layer: contract. Verifies packaged ledger authority passes for a full canonical ledger export."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    loaded = load_witness_package(package_root)

    result = verify_package_ledger(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "pass"
    assert result["failure_code"] is None


def test_package_ledger_rejects_missing_export(tmp_path: Path) -> None:
    """Layer: contract. Verifies missing packaged ledger bytes fail with the stable ledger code."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "ledger_export.json").unlink()

    loaded = load_witness_package(package_root)

    assert loaded.ok is False
    assert loaded.failure_code == "ledger_export_missing"


def test_package_ledger_rejects_changed_export_digest(tmp_path: Path) -> None:
    """Layer: contract. Verifies changed ledger bytes cannot satisfy stale bundle ledger evidence."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    ledger = json.loads((package_root / "ledger_export.json").read_text(encoding="utf-8"))
    ledger["canonical"]["ledger_hash"] = "changed"
    (package_root / "ledger_export.json").write_text(json.dumps(ledger, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_manifest(package_root)
    loaded = load_witness_package(package_root)

    result = verify_package_ledger(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "fail"
    assert result["failure_code"] == "ledger_export_digest_mismatch"


def test_package_ledger_rejects_partial_export_for_full_claim(tmp_path: Path) -> None:
    """Layer: contract. Verifies absence/completeness claims require export_scope=all."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    ledger = json.loads((package_root / "ledger_export.json").read_text(encoding="utf-8"))
    ledger["export_scope"] = "partial_view"
    ledger["verification"] = {"result": "partial_valid"}
    (package_root / "ledger_export.json").write_text(json.dumps(ledger, sort_keys=True) + "\n", encoding="utf-8")
    bundle = json.loads((package_root / "outward_witness_bundle.json").read_text(encoding="utf-8"))
    bundle["ledger_evidence"]["ledger_export_digest"] = file_sha256(package_root / "ledger_export.json")
    bundle["ledger_evidence"]["export_scope"] = "partial_view"
    (package_root / "outward_witness_bundle.json").write_text(json.dumps(bundle, sort_keys=True) + "\n", encoding="utf-8")
    _rewrite_manifest(package_root)
    loaded = load_witness_package(package_root)

    result = verify_package_ledger(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "fail"
    assert result["failure_code"] == "full_ledger_export_required"


def test_committed_artifact_verifies_packaged_bytes(tmp_path: Path) -> None:
    """Layer: contract. Verifies committed artifact digest is recomputed from package bytes."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    loaded = load_witness_package(package_root)

    result = verify_committed_artifact(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "pass"
    assert result["failure_code"] is None


def test_committed_artifact_missing_fails_with_stable_code(tmp_path: Path) -> None:
    """Layer: contract. Verifies missing committed artifact bytes fail closed."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "artifacts" / "committed_output").unlink()
    _rewrite_manifest(package_root)
    loaded = load_witness_package(package_root)

    result = verify_committed_artifact(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "fail"
    assert result["failure_code"] == "committed_artifact_missing"


def test_committed_artifact_digest_drift_fails_with_stable_code(tmp_path: Path) -> None:
    """Layer: contract. Verifies changed committed artifact bytes fail against bundle artifact refs."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "artifacts" / "committed_output").write_bytes(b"changed\n")
    _rewrite_manifest(package_root)
    loaded = load_witness_package(package_root)

    result = verify_committed_artifact(loaded.package)  # type: ignore[arg-type]

    assert result["result"] == "fail"
    assert result["failure_code"] == "artifact_digest_mismatch"
