from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_long_session_soak_tests import (
    check_long_session_soak_tests,
    evaluate_long_session_soak_tests,
    main,
)


# Layer: contract
def test_evaluate_long_session_soak_tests_passes_with_contract_minimum_turn_count() -> None:
    payload = evaluate_long_session_soak_tests(turn_count_override=100)
    assert payload["ok"] is True
    assert payload["check_count"] == 3
    assert payload["turn_count"] == 100


# Layer: integration
def test_check_long_session_soak_tests_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "long_session_soak_tests_check.json"
    exit_code, payload = check_long_session_soak_tests(out_path=out_path, turn_count_override=100)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "long_session_soak_tests_check.json"
    exit_code = main(["--out", str(out_path), "--turn-count", "100"])
    assert exit_code == 0
