# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_workspace_hygiene_rules import (
    check_workspace_hygiene_rules,
    evaluate_workspace_hygiene_rules,
    main,
)


# Layer: contract
def test_evaluate_workspace_hygiene_rules_passes_for_current_contract() -> None:
    payload = evaluate_workspace_hygiene_rules()
    assert payload["ok"] is True
    assert payload["rule_count"] >= 1


# Layer: integration
def test_check_workspace_hygiene_rules_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "workspace_hygiene_rules_check.json"
    exit_code, payload = check_workspace_hygiene_rules(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "workspace_hygiene_rules_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
