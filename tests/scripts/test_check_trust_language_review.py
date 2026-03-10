from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_trust_language_review import (
    check_trust_language_review,
    evaluate_trust_language_review,
    main,
)


# Layer: contract
def test_evaluate_trust_language_review_passes_for_current_policy() -> None:
    payload = evaluate_trust_language_review()
    assert payload["ok"] is True
    assert payload["claim_count"] >= 1


# Layer: integration
def test_check_trust_language_review_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "trust_language_review_check.json"
    exit_code, payload = check_trust_language_review(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "trust_language_review_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
