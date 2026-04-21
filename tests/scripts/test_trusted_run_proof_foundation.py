from __future__ import annotations

import json
from pathlib import Path

from scripts.proof.trusted_run_proof_foundation import (
    PROOF_FOUNDATION_SCHEMA_VERSION,
    build_trusted_run_proof_foundation_report,
    evaluate_offline_verifier_non_interference,
)
from scripts.proof.verify_trusted_run_proof_foundation import main as verify_trusted_run_proof_foundation_main


def test_proof_foundation_report_covers_all_workstream_one_targets() -> None:
    """Layer: contract. Verifies the canonical proof-foundation artifact covers the six fixed targets."""
    report = build_trusted_run_proof_foundation_report()

    assert report["schema_version"] == PROOF_FOUNDATION_SCHEMA_VERSION
    assert report["observed_result"] == "success"
    assert len(report["foundation_targets"]) == 6
    assert {item["status"] for item in report["foundation_targets"]} == {"pass"}
    assert report["non_interference"]["result"] == "pass"
    inspected = {item["relative_path"] for item in report["non_interference"]["inspected_files"]}
    assert "scripts/proof/governed_change_packet_contract.py" in inspected
    assert "scripts/proof/governed_change_packet_trusted_kernel.py" in inspected
    assert report["report_signature_digest"].startswith("sha256:")


def test_non_interference_check_fails_closed_on_unsafe_module(tmp_path: Path) -> None:
    """Layer: contract. Verifies unsafe imports and file writes fail the structural non-interference proof."""
    unsafe_module = tmp_path / "unsafe_verifier.py"
    unsafe_module.write_text(
        "import requests\n"
        "from pathlib import Path\n"
        "Path('unsafe.txt').write_text('drift', encoding='utf-8')\n",
        encoding="utf-8",
    )

    report = evaluate_offline_verifier_non_interference([unsafe_module], use_cache=False)

    assert report["result"] == "fail"
    assert any(hit["module"] == "requests" for hit in report["forbidden_import_hits"])
    assert any(hit["call"].endswith("write_text") for hit in report["forbidden_call_hits"])


def test_cli_writes_diff_ledger_output(tmp_path: Path) -> None:
    """Layer: integration. Verifies the proof-foundation CLI writes a stable diff-ledger JSON report."""
    output_path = tmp_path / "trusted_run_proof_foundation.json"

    exit_code = verify_trusted_run_proof_foundation_main(["--output", str(output_path)])

    assert exit_code == 0
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["observed_result"] == "success"
    assert len(persisted["foundation_targets"]) == 6
    assert isinstance(persisted.get("diff_ledger"), list)
