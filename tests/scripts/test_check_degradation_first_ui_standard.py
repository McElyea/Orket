from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_degradation_first_ui_standard import (
    check_degradation_first_ui_standard,
    evaluate_degradation_first_ui_standard,
    main,
)


# Layer: contract
def test_evaluate_degradation_first_ui_standard_passes() -> None:
    payload = evaluate_degradation_first_ui_standard()
    assert payload["ok"] is True
    assert payload["check_count"] == 4


# Layer: integration
def test_check_degradation_first_ui_standard_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "degradation_first_ui_standard_check.json"
    exit_code, payload = check_degradation_first_ui_standard(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "degradation_first_ui_standard_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
