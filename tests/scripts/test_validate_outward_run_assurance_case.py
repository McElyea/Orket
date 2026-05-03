from __future__ import annotations

from pathlib import Path

from scripts.proof.validate_outward_run_assurance_case import validate_assurance_case


def _doc(row: str) -> str:
    return "\n".join(
        [
            "| Claim ID | Claim | Compare Scope | Operator Surface | Allowed Posture | Invariant IDs | Authority Evidence | Derived / Support Evidence | Verifier Command | Current Blocker |",
            "|---|---|---|---|---|---|---|---|---|---|",
            row,
            "",
        ]
    )


def _write(path: Path, row: str) -> Path:
    path.write_text(_doc(row), encoding="utf-8")
    return path


def test_valid_assurance_case_row_passes(tmp_path: Path) -> None:
    """Layer: contract. Verifies a package-consuming assurance row passes validation."""
    path = _write(
        tmp_path / "case.md",
        "| ORP-CLAIM-X | claim | scope | `outward_run_witness_report.v1` | tier | ORP-INV-001 | packaged ledger bytes | summary | python scripts/proof/verify_outward_run_witness_package.py --package <package> | none |",
    )

    assert validate_assurance_case(path)["result"] == "accepted"


def test_missing_authority_refs_fail(tmp_path: Path) -> None:
    """Layer: contract. Verifies missing authority evidence is rejected."""
    path = _write(
        tmp_path / "case.md",
        "| ORP-CLAIM-X | claim | scope | `outward_run_witness_report.v1` | tier | ORP-INV-001 |  | summary | python scripts/proof/verify_outward_run_witness_package.py --package <package> | none |",
    )

    assert "missing_authority_refs" in validate_assurance_case(path)["missing_evidence"]


def test_missing_invariant_ids_fail(tmp_path: Path) -> None:
    """Layer: contract. Verifies rows without ORP invariant ids are rejected."""
    path = _write(
        tmp_path / "case.md",
        "| ORP-CLAIM-X | claim | scope | `outward_run_witness_report.v1` | tier |  | packaged ledger bytes | summary | python scripts/proof/verify_outward_run_witness_package.py --package <package> | none |",
    )

    assert "missing_invariant_ids" in validate_assurance_case(path)["missing_evidence"]


def test_support_only_authority_substitution_fails(tmp_path: Path) -> None:
    """Layer: contract. Verifies support-only authority substitution is rejected."""
    path = _write(
        tmp_path / "case.md",
        "| ORP-CLAIM-X | claim | scope | `outward_run_witness_report.v1` | tier | ORP-INV-001 | support-only run summary projection | summary | python scripts/proof/verify_outward_run_witness_package.py --package <package> | none |",
    )

    assert "support_only_authority_substitution" in validate_assurance_case(path)["missing_evidence"]


def test_bundle_only_verifier_command_fails(tmp_path: Path) -> None:
    """Layer: contract. Verifies bundle-only verifier commands cannot authorize proof claims."""
    path = _write(
        tmp_path / "case.md",
        "| ORP-CLAIM-X | claim | scope | `outward_run_witness_report.v1` | tier | ORP-INV-001 | packaged ledger bytes | summary | python scripts/proof/verify_outward_run_witness_bundle.py --bundle bundle.json | none |",
    )

    assert "bundle_only_verifier_command" in validate_assurance_case(path)["missing_evidence"]
