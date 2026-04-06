# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.check_environment_parity_checklist import (
    check_environment_parity_checklist,
    evaluate_environment_parity_checklist,
)


# Layer: contract
def test_environment_parity_checklist_passes_with_empty_env_and_no_required_keys() -> None:
    payload = evaluate_environment_parity_checklist(environment={}, required_keys=[])
    assert payload["ok"] is True
    checks = {row["check"] for row in payload["checks"]}
    assert "protocol_network_mode_env_valid" in checks


# Layer: contract
def test_environment_parity_checklist_fails_on_invalid_network_mode_value() -> None:
    payload = evaluate_environment_parity_checklist(
        environment={"ORKET_PROTOCOL_NETWORK_MODE": "internet"},
        required_keys=[],
    )
    assert payload["ok"] is False
    row = next(row for row in payload["checks"] if row["check"] == "protocol_network_mode_env_valid")
    assert row["ok"] is False


# Layer: contract
def test_environment_parity_checklist_fails_on_invalid_provider_model_quarantine_tokens() -> None:
    payload = evaluate_environment_parity_checklist(
        environment={"ORKET_PROVIDER_MODEL_QUARANTINE": "badtoken,ollama:"},
        required_keys=[],
    )
    assert payload["ok"] is False
    row = next(row for row in payload["checks"] if row["check"] == "provider_model_quarantine_env_tokens_valid")
    assert row["ok"] is False
    assert row["invalid_tokens"] == ["badtoken", "ollama:"]


# Layer: integration
def test_environment_parity_checklist_writes_diff_ledger_payload(tmp_path: Path) -> None:
    out_path = tmp_path / "parity.json"
    exit_code, payload = check_environment_parity_checklist(
        environment={"ORKET_PROTOCOL_NETWORK_MODE": "off"},
        required_keys=["ORKET_PROTOCOL_NETWORK_MODE"],
        out_path=out_path,
    )
    assert exit_code == 0
    assert payload["ok"] is True
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written
