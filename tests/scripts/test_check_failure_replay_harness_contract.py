# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_failure_replay_harness_contract import (
    check_failure_replay_harness_contract,
    evaluate_failure_replay_harness_contract,
    main,
)


# Layer: contract
def test_evaluate_failure_replay_harness_contract_passes_for_current_contract() -> None:
    payload = evaluate_failure_replay_harness_contract()
    assert payload["ok"] is True
    assert payload["required_output_field_count"] >= 1


# Layer: integration
def test_check_failure_replay_harness_contract_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "failure_replay_harness_contract_check.json"
    exit_code, payload = check_failure_replay_harness_contract(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "failure_replay_harness_contract_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
