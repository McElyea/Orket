# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_result_error_invariants import (
    check_result_error_invariants,
    evaluate_result_error_invariants,
    main,
)


# Layer: contract
def test_evaluate_result_error_invariants_passes_for_current_contract() -> None:
    payload = evaluate_result_error_invariants()
    assert payload["ok"] is True
    assert payload["forbidden_status_count"] >= 1
    assert payload["behavior_case_count"] >= 1


# Layer: integration
def test_check_result_error_invariants_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "result_error_invariants_check.json"
    exit_code, payload = check_result_error_invariants(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "result_error_invariants_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
