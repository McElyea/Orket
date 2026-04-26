from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.core.domain.outward_ledger import verify_ledger_export
from tests.helpers.outward_model import patch_outward_model_client


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "phase6-control-plane.sqlite3"
    policy_path = tmp_path / "outbound-policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "pii_field_paths": ["items.*.args_preview.path"],
                "forbidden_patterns": ["BLOCKME"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_CONFIG_PATH", str(policy_path))
    patch_outward_model_client(monkeypatch, args={"path": "phase6.txt", "content": "safe"})
    return TestClient(api_module.create_api_app(project_root=tmp_path))


@pytest.mark.integration
def test_phase6_policy_gate_filters_approval_events_summary_and_ledger(tmp_path, monkeypatch) -> None:
    """Layer: integration. Verifies configured policy gate redaction on outward operator API surfaces."""
    client = _client(tmp_path, monkeypatch)
    try:
        approval_run = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json={
                "run_id": "run-phase6-approval",
                "task": {
                    "description": "Approval BLOCKME",
                    "instruction": "Call write_file",
                    "acceptance_contract": {
                        "governed_tool_call": {
                            "tool": "write_file",
                            "args": {"path": "phase6.txt", "content": "safe"},
                        }
                    },
                },
                "policy_overrides": {"approval_required_tools": ["write_file"]},
            },
        )
        approvals = client.get("/v1/approvals", headers={"X-API-Key": "test-key"}, params={"status": "pending"})
        events = client.get("/v1/runs/run-phase6-approval/events", headers={"X-API-Key": "test-key"})

        failed_run = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json={
                "run_id": "run-phase6-failed",
                "task": {
                    "description": "Failure BLOCKME",
                    "instruction": "Call unregistered tool",
                    "acceptance_contract": {
                        "governed_tool_call": {
                            "tool": "not_registered_BLOCKME",
                            "args": {"path": "unused.txt"},
                        }
                    },
                },
                "policy_overrides": {"approval_required_tools": ["not_registered_BLOCKME"]},
            },
        )
        summary = client.get("/v1/runs/run-phase6-failed/summary", headers={"X-API-Key": "test-key"})
        ledger = client.get("/v1/runs/run-phase6-failed/ledger", headers={"X-API-Key": "test-key"})

        assert approval_run.status_code == 200
        assert approvals.status_code == 200
        assert approvals.json()["items"][0]["args_preview"]["path"] == "[REDACTED]"
        assert events.status_code == 200
        assert "BLOCKME" not in str(events.json())
        assert failed_run.status_code == 200
        assert failed_run.json()["status"] == "failed"
        assert summary.status_code == 200
        assert "BLOCKME" not in str(summary.json())
        assert ledger.status_code == 200
        assert "BLOCKME" not in str(ledger.json())
        assert ledger.json()["export_scope"] == "partial_view"
        assert ledger.json()["verification"]["result"] == "partial_valid"
        assert verify_ledger_export(ledger.json())["result"] == "partial_valid"
    finally:
        client.close()
