from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_tool_invocation_policy_contract import (
    check_tool_invocation_policy_contract,
    evaluate_tool_invocation_policy_contract,
    main,
)


# Layer: contract
def test_evaluate_tool_invocation_policy_contract_passes_for_current_contract() -> None:
    payload = evaluate_tool_invocation_policy_contract()
    assert payload["ok"] is True
    assert payload["run_type_count"] >= 1


# Layer: integration
def test_check_tool_invocation_policy_contract_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "tool_invocation_policy_contract_check.json"
    exit_code, payload = check_tool_invocation_policy_contract(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "tool_invocation_policy_contract_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
