# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_runtime_truth_contract_drift import (
    check_runtime_truth_contract_drift,
    main,
)


# Layer: integration
def test_check_runtime_truth_contract_drift_writes_report_and_passes(tmp_path: Path) -> None:
    out_path = tmp_path / "drift_report.json"
    exit_code, payload = check_runtime_truth_contract_drift(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["ok"] is True


# Layer: contract
def test_check_runtime_truth_contract_drift_main_returns_success() -> None:
    assert main([]) == 0
