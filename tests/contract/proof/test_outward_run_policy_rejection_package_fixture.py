from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.outward_run_witness_contract import (
    COMPARE_SCOPE_POLICY_REJECTED,
    compute_package_digest,
    file_sha256,
)
from scripts.proof.verify_outward_run_witness_package import verify_package

BASE_POLICY_REJECTED = Path("tests/proof_fixtures/outward_run/base_policy_rejected_package")


def test_policy_rejection_fixture_verifies_offline() -> None:
    """Layer: contract. Verifies the frozen policy-rejection fixture is accepted from package bytes."""
    report = verify_package(BASE_POLICY_REJECTED, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert report["result"] == "accepted"
    assert report["missing_evidence"] == []


def test_policy_rejection_fixture_has_full_ledger_and_no_committed_artifact() -> None:
    """Layer: contract. Verifies fixture absence proof uses full ledger bytes without fabricated effects."""
    manifest = json.loads((BASE_POLICY_REJECTED / "manifest.json").read_text(encoding="utf-8"))
    ledger = json.loads((BASE_POLICY_REJECTED / "ledger_export.json").read_text(encoding="utf-8"))
    bundle = json.loads((BASE_POLICY_REJECTED / "outward_witness_bundle.json").read_text(encoding="utf-8"))

    assert ledger["export_scope"] == "all"
    assert manifest["artifact_paths"] == {}
    assert bundle["artifact_refs"] == []
    assert bundle["approval_authority"] == []
    assert not (BASE_POLICY_REJECTED / "artifacts" / "committed_output").exists()


def test_policy_rejection_fixture_rejects_without_policy_authority(tmp_path: Path) -> None:
    """Layer: contract. Verifies removing policy authority evidence rejects the fixture."""
    target = tmp_path / "package"
    _copy_package(BASE_POLICY_REJECTED, target)
    bundle_path = target / "outward_witness_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["policy_rejection_authority"] = []
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest["file_digests"] = {
        "outward_witness_bundle.json": file_sha256(target / "outward_witness_bundle.json"),
        "ledger_export.json": file_sha256(target / "ledger_export.json"),
    }
    manifest["package_digest"] = compute_package_digest(manifest)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = verify_package(target, scope=COMPARE_SCOPE_POLICY_REJECTED)

    assert report["result"] == "rejected"
    assert "policy_rejection_event_missing" in report["missing_evidence"]


def _copy_package(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for name in ["manifest.json", "outward_witness_bundle.json", "ledger_export.json"]:
        (target / name).write_bytes((source / name).read_bytes())
