# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.runtime.retry_classification_policy import retry_classification_policy_snapshot
from scripts.governance import check_retry_classification_policy as retry_policy_module
from scripts.governance.check_retry_classification_policy import (
    check_retry_classification_policy,
    evaluate_retry_classification_policy,
    main,
    validate_retry_classification_policy_report,
)


# Layer: contract
def test_evaluate_retry_classification_policy_passes_for_current_contract() -> None:
    payload = evaluate_retry_classification_policy()
    assert payload["ok"] is True
    assert payload["signal_count"] >= 1


# Layer: contract
def test_validate_retry_classification_policy_report_accepts_current_payload() -> None:
    payload = validate_retry_classification_policy_report(evaluate_retry_classification_policy())
    assert payload["ok"] is True
    assert payload["signal_count"] >= 1


# Layer: contract
def test_validate_retry_classification_policy_report_rejects_missing_signal_list() -> None:
    with pytest.raises(ValueError, match="E_RETRY_POLICY_REPORT_SIGNALS_INVALID"):
        _ = validate_retry_classification_policy_report(
            {
                "schema_version": "1.0",
                "ok": True,
                "signal_count": 1,
                "snapshot": retry_classification_policy_snapshot(),
            }
        )


# Layer: integration
def test_validate_retry_classification_policy_report_rejects_invalid_failure_snapshot() -> None:
    with pytest.raises(ValueError, match="E_RETRY_POLICY_REPORT_SNAPSHOT_INVALID:E_RETRY_POLICY_SCHEMA_VERSION_INVALID"):
        _ = validate_retry_classification_policy_report(
            {
                "schema_version": "1.0",
                "ok": False,
                "error": "E_RETRY_POLICY_REPORT_SIGNALS_INVALID",
                "snapshot": {},
            }
        )


# Layer: integration
def test_check_retry_classification_policy_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "retry_policy_check.json"
    exit_code, payload = check_retry_classification_policy(out_path=out_path)
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_check_retry_classification_policy_normalizes_malformed_report_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "retry_policy_check.json"
    monkeypatch.setattr(
        retry_policy_module,
        "evaluate_retry_classification_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": True,
            "signal_count": 0,
            "snapshot": retry_classification_policy_snapshot(),
        },
    )

    exit_code, payload = check_retry_classification_policy(out_path=out_path)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"] == "E_RETRY_POLICY_REPORT_SIGNALS_INVALID"
    assert payload["snapshot"] == retry_classification_policy_snapshot()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["ok"] is False
    assert written["error"] == "E_RETRY_POLICY_REPORT_SIGNALS_INVALID"
    assert written["snapshot"] == retry_classification_policy_snapshot()
    assert "diff_ledger" in written


# Layer: integration
def test_check_retry_classification_policy_normalizes_invalid_snapshot_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out_path = tmp_path / "retry_policy_check.json"
    monkeypatch.setattr(
        retry_policy_module,
        "evaluate_retry_classification_policy",
        lambda: {
            "schema_version": "1.0",
            "ok": False,
            "error": "E_RETRY_POLICY_REPORT_SIGNALS_INVALID",
            "snapshot": {},
        },
    )

    exit_code, payload = check_retry_classification_policy(out_path=out_path)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"] == "E_RETRY_POLICY_REPORT_SNAPSHOT_INVALID:E_RETRY_POLICY_SCHEMA_VERSION_INVALID"
    assert payload["snapshot"] == retry_classification_policy_snapshot()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["ok"] is False
    assert written["error"] == "E_RETRY_POLICY_REPORT_SNAPSHOT_INVALID:E_RETRY_POLICY_SCHEMA_VERSION_INVALID"
    assert written["snapshot"] == retry_classification_policy_snapshot()
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success(tmp_path: Path) -> None:
    out_path = tmp_path / "retry_policy_check.json"
    exit_code = main(["--out", str(out_path)])
    assert exit_code == 0
