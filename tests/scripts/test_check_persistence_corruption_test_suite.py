# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_persistence_corruption_test_suite import (
    check_persistence_corruption_test_suite,
    evaluate_persistence_corruption_test_suite,
    main,
)


# Layer: contract
def test_evaluate_persistence_corruption_test_suite_passes() -> None:
    payload = evaluate_persistence_corruption_test_suite()
    assert payload["ok"] is True
    assert payload["check_count"] == 3


# Layer: integration
def test_check_persistence_corruption_test_suite_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "persistence_corruption_test_suite_check.json"
    exit_code, payload = check_persistence_corruption_test_suite(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "persistence_corruption_test_suite_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
