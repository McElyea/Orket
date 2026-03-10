from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_release_confidence_scorecard import (
    check_release_confidence_scorecard,
    evaluate_release_confidence_scorecard,
    main,
)


# Layer: contract
def test_evaluate_release_confidence_scorecard_passes_for_current_contract() -> None:
    payload = evaluate_release_confidence_scorecard()
    assert payload["ok"] is True
    assert payload["dimension_count"] >= 1


# Layer: integration
def test_check_release_confidence_scorecard_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "release_confidence_scorecard_check.json"
    exit_code, payload = check_release_confidence_scorecard(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "release_confidence_scorecard_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
