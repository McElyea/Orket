# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_decision_record_operating_principles_contract import (
    check_decision_record_operating_principles_contract,
    evaluate_decision_record_operating_principles_contract,
    main,
)


# Layer: contract
def test_evaluate_decision_record_operating_principles_contract_passes() -> None:
    payload = evaluate_decision_record_operating_principles_contract(workspace=Path().resolve())
    assert payload["ok"] is True
    assert payload["check_count"] == 2


# Layer: integration
def test_check_decision_record_operating_principles_contract_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "decision_record_operating_principles_contract_check.json"
    exit_code, payload = check_decision_record_operating_principles_contract(
        workspace=Path().resolve(),
        out_path=out_path,
    )
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "decision_record_operating_principles_contract_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
