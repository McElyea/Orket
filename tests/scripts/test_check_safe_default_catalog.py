# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_safe_default_catalog import (
    check_safe_default_catalog,
    evaluate_safe_default_catalog,
    main,
)


# Layer: contract
def test_evaluate_safe_default_catalog_passes_for_current_contract() -> None:
    payload = evaluate_safe_default_catalog()
    assert payload["ok"] is True
    assert payload["default_key_count"] >= 1
    assert "protocol_network_mode" in payload["default_keys"]


# Layer: integration
def test_check_safe_default_catalog_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "safe_default_catalog_check.json"
    exit_code, payload = check_safe_default_catalog(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "safe_default_catalog_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
