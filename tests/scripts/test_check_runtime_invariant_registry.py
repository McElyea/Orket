# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_runtime_invariant_registry import (
    check_runtime_invariant_registry,
    evaluate_runtime_invariant_registry,
    main,
)


# Layer: contract
def test_evaluate_runtime_invariant_registry_passes_for_default_doc() -> None:
    payload = evaluate_runtime_invariant_registry()
    assert payload["ok"] is True
    assert payload["invariant_count"] >= 1
    assert "INV-001" in payload["invariant_ids"]


# Layer: integration
def test_check_runtime_invariant_registry_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_invariant_registry_check.json"
    exit_code, payload = check_runtime_invariant_registry(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "runtime_invariant_registry_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
