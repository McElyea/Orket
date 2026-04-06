# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_observability_redaction_tests import (
    check_observability_redaction_tests,
    evaluate_observability_redaction_tests,
    main,
)


# Layer: contract
def test_evaluate_observability_redaction_tests_passes_for_current_redaction_paths() -> None:
    payload = evaluate_observability_redaction_tests()
    assert payload["ok"] is True
    assert payload["check_count"] >= 1


# Layer: integration
def test_check_observability_redaction_tests_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "observability_redaction_tests_check.json"
    exit_code, payload = check_observability_redaction_tests(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "observability_redaction_tests_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
