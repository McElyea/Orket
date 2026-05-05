from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from scripts.proof.trust_handoff_emitter import emit_trust_handoff_package
from tests.helpers.outward_model import patch_outward_model_client

SOURCE_RUN_ID = "run-live-proof"
SOURCE_AGENT_ID = "outward-agent"
SCOPE_ID = "scope-packet1"


def _client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, str]:
    db_path = tmp_path / "api-handoff.sqlite3"
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(db_path))
    patch_outward_model_client(monkeypatch, args={"path": "api-b.txt", "content": "api b"})
    return TestClient(api_module.create_api_app(project_root=tmp_path)), str(db_path)


def _package(tmp_path, *, target_agent_id: str):
    out = tmp_path / f"handoff-{target_agent_id}"
    emit_trust_handoff_package(
        source_run_id=SOURCE_RUN_ID,
        target_agent_id=target_agent_id,
        scope_id=SCOPE_ID,
        out_dir=out,
    )
    return out


def _payload(run_id: str, package_path, *, complete: bool = True) -> dict:
    acceptance = {
        "handoff_required": True,
        "governed_tool_call": {"tool": "write_file", "args": {"path": "api-b.txt", "content": "api b"}},
    }
    if complete:
        acceptance.update(
            {
                "handoff_policy_compatibility_scope_id": SCOPE_ID,
                "handoff_envelope_package_path": str(package_path),
                "expected_source_agent_id": SOURCE_AGENT_ID,
            }
        )
    return {
        "run_id": run_id,
        "task": {"description": "B consumes A output", "instruction": "Call write_file", "acceptance_contract": acceptance},
        "policy_overrides": {"approval_required_tools": ["write_file"]},
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_handoff_required_submission_verifies_before_start(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies API submission can require Packet 1 handoff admission."""
    client, db_path = _client(tmp_path, monkeypatch)
    package = _package(tmp_path, target_agent_id="run-api-handoff")
    try:
        response = client.post("/v1/runs", headers={"X-API-Key": "test-key"}, json=_payload("run-api-handoff", package))
        assert response.status_code == 200
        assert response.json()["status"] == "approval_required"
    finally:
        client.close()

    events = await OutwardRunEventStore(db_path).list_for_run("run-api-handoff")
    event_types = [event.event_type for event in events]
    assert event_types.index("trust_handoff_verified") < event_types.index("run_started")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_incomplete_handoff_contract_fails_closed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies incomplete API handoff contracts reject durably before run_started."""
    client, db_path = _client(tmp_path, monkeypatch)
    try:
        response = client.post(
            "/v1/runs",
            headers={"X-API-Key": "test-key"},
            json=_payload("run-api-handoff-incomplete", tmp_path / "missing", complete=False),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["stop_reason"] == "handoff_acceptance_contract_incomplete"
    finally:
        client.close()

    events = await OutwardRunEventStore(db_path).list_for_run("run-api-handoff-incomplete")
    event_types = [event.event_type for event in events]
    assert event_types == ["run_submitted", "trust_handoff_rejected", "run_completed"]
