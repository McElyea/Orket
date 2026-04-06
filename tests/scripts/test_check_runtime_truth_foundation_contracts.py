# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_runtime_truth_foundation_contracts import (
    check_runtime_truth_foundation_contracts,
    evaluate_runtime_truth_foundation_contracts,
    main,
)


# Layer: contract
def test_evaluate_runtime_truth_foundation_contracts_passes_for_current_contracts() -> None:
    payload = evaluate_runtime_truth_foundation_contracts()
    assert payload["ok"] is True
    checks = {row["check"] for row in payload["checks"]}
    assert "runtime_status_vocabulary_contract_valid" in checks
    assert "degradation_taxonomy_contract_valid" in checks
    assert "fail_behavior_registry_contract_valid" in checks


# Layer: integration
def test_check_runtime_truth_foundation_contracts_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_truth_foundation_contracts_check.json"
    exit_code, payload = check_runtime_truth_foundation_contracts(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_truth_foundation_contracts_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
