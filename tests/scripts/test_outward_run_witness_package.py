from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.outward_run_witness_contract import compute_package_digest, file_sha256
from scripts.proof.outward_run_witness_package import bundle_only_introspection, load_witness_package


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _minimal_package(root: Path) -> Path:
    root.mkdir(parents=True)
    _write_json(
        root / "ledger_export.json",
        {
            "schema_version": "ledger_export.v1",
            "export_scope": "all",
            "run_id": "run-test",
            "canonical": {"event_count": 0, "ledger_hash": "GENESIS", "genesis": "GENESIS"},
            "events": [],
            "omitted_spans": [],
        },
    )
    artifact = root / "artifacts" / "committed_output"
    artifact.parent.mkdir()
    artifact.write_bytes(b"committed\n")
    _write_json(
        root / "outward_witness_bundle.json",
        {
            "schema_version": "outward_run.witness_bundle.v1",
            "bundle_id": "bundle-test",
            "run_id": "run-test",
            "compare_scope": "outward_run_write_file_approved_v1",
            "operator_surface": "outward_run_witness_report.v1",
            "claim_tier_request": "outward_lab_only",
            "ledger_evidence": {
                "ledger_export_schema": "ledger_export.v1",
                "run_id": "run-test",
                "event_count": 0,
                "export_scope": "all",
                "ledger_hash": "GENESIS",
                "events": [],
                "ledger_export_digest": file_sha256(root / "ledger_export.json"),
                "ledger_export_package_path": "ledger_export.json",
            },
            "artifact_refs": [
                {
                    "artifact_role": "committed_output",
                    "path": "approved.txt",
                    "package_path": "artifacts/committed_output",
                    "digest": file_sha256(artifact),
                    "classification": "authority",
                }
            ],
            "package_refs": {
                "ledger_export_path": "ledger_export.json",
                "committed_output_path": "artifacts/committed_output",
            },
        },
    )
    manifest = {
        "schema_version": "outward_run_witness_package.v1",
        "package_id": "package-test",
        "compare_scope": "outward_run_write_file_approved_v1",
        "bundle_path": "outward_witness_bundle.json",
        "ledger_export_path": "ledger_export.json",
        "artifact_paths": {"committed_output": "artifacts/committed_output"},
        "file_digests": {
            "outward_witness_bundle.json": file_sha256(root / "outward_witness_bundle.json"),
            "ledger_export.json": file_sha256(root / "ledger_export.json"),
            "artifacts/committed_output": file_sha256(artifact),
        },
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    _write_json(root / "manifest.json", manifest)
    return root


def test_package_loader_accepts_minimal_valid_package(tmp_path: Path) -> None:
    """Layer: unit. Verifies the package loader accepts package-local manifest, bundle, ledger, and artifact bytes."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")

    loaded = load_witness_package(package_root)

    assert loaded.ok is True
    assert loaded.failure_code is None
    assert loaded.package is not None
    assert loaded.package.bundle["run_id"] == "run-test"
    assert loaded.package.artifacts["committed_output"] == b"committed\n"


def test_package_loader_fails_closed_for_missing_manifest(tmp_path: Path) -> None:
    """Layer: unit. Verifies missing manifest fails with a stable package code."""
    package_root = tmp_path / "outward_run_witness_package.v1"
    package_root.mkdir()

    loaded = load_witness_package(package_root)

    assert loaded.ok is False
    assert loaded.failure_code == "package_manifest_missing"


def test_package_loader_fails_closed_for_missing_bundle(tmp_path: Path) -> None:
    """Layer: unit. Verifies missing bundle fails before any proof-shaped result is possible."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "outward_witness_bundle.json").unlink()

    loaded = load_witness_package(package_root)

    assert loaded.ok is False
    assert loaded.failure_code == "bundle_missing"


def test_package_loader_fails_closed_for_digest_drift(tmp_path: Path) -> None:
    """Layer: unit. Verifies package bytes are rehashed and compared with manifest digest material."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    (package_root / "artifacts" / "committed_output").write_text("changed\n", encoding="utf-8")

    loaded = load_witness_package(package_root)

    assert loaded.ok is False
    assert loaded.failure_code == "package_manifest_digest_mismatch"


def test_package_loader_rejects_package_ref_escape(tmp_path: Path) -> None:
    """Layer: unit. Verifies package refs resolving outside the package root are rejected."""
    package_root = _minimal_package(tmp_path / "outward_run_witness_package.v1")
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    manifest["artifact_paths"]["committed_output"] = "../escape.txt"
    manifest["package_digest"] = compute_package_digest(manifest)
    _write_json(package_root / "manifest.json", manifest)

    loaded = load_witness_package(package_root)

    assert loaded.ok is False
    assert loaded.failure_code == "package_ref_outside_package"


def test_bundle_only_introspection_cannot_accept_proof_claim() -> None:
    """Layer: unit. Verifies bundle-only loading remains schema/introspection-only."""
    report = bundle_only_introspection({"schema_version": "outward_run.witness_bundle.v1"})

    assert report["accepted"] is False
    assert report["result"] != "accepted"
    assert "package_required_for_proof" in report["missing_evidence"]
