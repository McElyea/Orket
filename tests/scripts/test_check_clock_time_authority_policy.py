# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_clock_time_authority_policy import (
    check_clock_time_authority_policy,
    evaluate_clock_time_authority_policy,
    main,
)


# Layer: contract
def test_evaluate_clock_time_authority_policy_passes_for_current_contract() -> None:
    payload = evaluate_clock_time_authority_policy()
    assert payload["ok"] is True
    assert payload["defaults"]["clock_mode"] == "wall"


# Layer: integration
def test_check_clock_time_authority_policy_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "clock_time_authority_policy_check.json"
    exit_code, payload = check_clock_time_authority_policy(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "clock_time_authority_policy_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
