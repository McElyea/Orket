from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.governance.check_runtime_boundary_audit_checklist import (
    check_runtime_boundary_audit_checklist,
    evaluate_runtime_boundary_audit_checklist,
    main,
)


# Layer: contract
def test_evaluate_runtime_boundary_audit_checklist_passes_in_repo_workspace() -> None:
    payload = evaluate_runtime_boundary_audit_checklist(workspace=Path(".").resolve())
    assert payload["ok"] is True
    assert payload["boundary_count"] >= 1


# Layer: contract
def test_evaluate_runtime_boundary_audit_checklist_fails_for_missing_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.governance import check_runtime_boundary_audit_checklist as checker

    original = checker.runtime_boundary_audit_checklist_snapshot

    def _patched_snapshot() -> dict[str, object]:
        payload = original()
        payload["boundaries"][0]["path"] = "missing/path.py"
        return payload

    monkeypatch.setattr(checker, "runtime_boundary_audit_checklist_snapshot", _patched_snapshot)
    payload = evaluate_runtime_boundary_audit_checklist(workspace=tmp_path.resolve())
    assert payload["ok"] is False
    assert "E_RUNTIME_BOUNDARY_PATH_MISSING" in str(payload["error"])


# Layer: integration
def test_check_runtime_boundary_audit_checklist_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "boundary_check.json"
    exit_code, payload = check_runtime_boundary_audit_checklist(
        workspace=Path(".").resolve(),
        out_path=out_path,
    )
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "boundary_check.json"
    exit_code = main(["--workspace", str(Path(".").resolve()), "--out", str(out_path)])
    assert exit_code == 0
