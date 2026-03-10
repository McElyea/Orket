from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_runtime_config_ownership_map import (
    check_runtime_config_ownership_map,
    evaluate_runtime_config_ownership_map,
    main,
)


# Layer: contract
def test_evaluate_runtime_config_ownership_map_passes_for_current_contract() -> None:
    payload = evaluate_runtime_config_ownership_map()
    assert payload["ok"] is True
    assert payload["config_key_count"] >= 1
    assert "ORKET_STATE_BACKEND_MODE" in payload["config_keys"]


# Layer: integration
def test_check_runtime_config_ownership_map_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_config_ownership_map_check.json"
    exit_code, payload = check_runtime_config_ownership_map(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_config_ownership_map_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
