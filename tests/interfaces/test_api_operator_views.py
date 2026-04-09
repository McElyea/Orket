from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orket.interfaces.api as api_module
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.run_summary import build_run_summary_payload
from orket.schema import CardStatus

_STARTED_AT = "2036-03-05T12:00:00+00:00"
_FINALIZED_AT = "2036-03-05T12:00:05+00:00"


def _run_identity(*, run_id: str, workload: str = "cards-runtime") -> dict[str, str | bool]:
    return {
        "run_id": run_id,
        "workload": workload,
        "start_time": _STARTED_AT,
        "identity_scope": "session_bootstrap",
        "projection_source": "session_bootstrap_artifacts",
        "projection_only": True,
    }


def _client() -> TestClient:
    return TestClient(api_module.app)


@pytest.mark.asyncio
async def test_cards_and_runs_operator_views_project_truthful_outcomes(monkeypatch, tmp_path: Path) -> None:
    """Layer: integration. Verifies the card viewer slice is backed by stable operator view models instead of raw summary spelunking."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    real_engine = OrchestrationEngine(
        workspace_root=workspace_root,
        db_path=str(tmp_path / "runtime.db"),
    )
    monkeypatch.setattr(api_module, "engine", real_engine)

    verified_session_id = "RUN-VERIFIED-1"
    failed_session_id = "RUN-FAILED-1"
    for session_id in (verified_session_id, failed_session_id):
        await real_engine.sessions.start_session(
            session_id,
            {"type": "epic", "name": session_id, "department": "core", "task_input": "demo"},
        )

    await real_engine.cards.save(
        {
            "id": "CARD-VERIFIED",
            "session_id": verified_session_id,
            "build_id": "BUILD-1",
            "seat": "COD-1",
            "summary": "Verified card",
            "priority": 2.0,
            "params": {
                "execution_profile": "builder_guard_app_v1",
                "artifact_contract": {
                    "kind": "app",
                    "primary_output": "agent_output/main.py",
                    "entrypoint_path": "agent_output/main.py",
                    "required_write_paths": ["agent_output/main.py"],
                },
            },
        }
    )
    await real_engine.cards.save(
        {
            "id": "CARD-FAILED",
            "session_id": failed_session_id,
            "build_id": "BUILD-2",
            "seat": "COD-1",
            "summary": "Blocked card",
            "priority": 2.0,
            "params": {
                "execution_profile": "odr_prebuild_builder_guard_v1",
                "artifact_contract": {
                    "kind": "artifact",
                    "primary_output": "agent_output/out.txt",
                    "required_write_paths": ["agent_output/out.txt"],
                },
            },
        }
    )
    await real_engine.cards.update_status("CARD-VERIFIED", CardStatus.DONE)
    await real_engine.cards.update_status("CARD-FAILED", CardStatus.BLOCKED)

    verified_artifacts = {
        "run_identity": _run_identity(run_id=verified_session_id),
        "packet1_facts": {
            "primary_work_artifact_output": {"id": "agent_output/main.py", "kind": "artifact"},
        },
        "packet2_facts": {
            "source_attribution": {
                "mode": "required",
                "high_stakes": False,
                "synthesis_status": "verified",
                "artifact_provenance_verified": True,
                "receipt_artifact_path": "agent_output/source_attribution_receipt.json",
            }
        },
        "cards_runtime_facts": {
            "execution_profile": "builder_guard_app_v1",
            "stop_reason": "completed",
            "resolution_state": "resolved",
            "artifact_contract": {
                "kind": "app",
                "primary_output": "agent_output/main.py",
                "entrypoint_path": "agent_output/main.py",
                "required_write_paths": ["agent_output/main.py"],
                "review_read_paths": ["agent_output/main.py"],
                "deployment_enabled": True,
            },
        },
        "runtime_verification_path": "agent_output/verification/runtime_verification.json",
    }
    verified_summary = build_run_summary_payload(
        run_id=verified_session_id,
        status="done",
        failure_reason=None,
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=[],
        artifacts=verified_artifacts,
    )
    await real_engine.run_ledger.start_run(
        session_id=verified_session_id,
        run_type="epic",
        run_name="verified",
        department="core",
        build_id="BUILD-1",
        summary={"phase": "execute"},
        artifacts={"run_identity": verified_artifacts["run_identity"]},
    )
    await real_engine.run_ledger.finalize_run(
        session_id=verified_session_id,
        status="done",
        summary=verified_summary,
        artifacts=verified_artifacts,
    )

    failed_artifacts = {
        "run_identity": _run_identity(run_id=failed_session_id),
        "cards_runtime_facts": {
            "execution_profile": "odr_prebuild_builder_guard_v1",
            "resolution_state": "resolved",
            "odr_active": True,
            "audit_mode": "self_audit_fallback",
            "odr_stop_reason": "UNRESOLVED_DECISIONS",
            "odr_pending_decisions": 2,
        },
    }
    failed_summary = build_run_summary_payload(
        run_id=failed_session_id,
        status="failed",
        failure_reason="UNRESOLVED_DECISIONS",
        started_at=_STARTED_AT,
        ended_at=_FINALIZED_AT,
        tool_names=[],
        artifacts=failed_artifacts,
    )
    await real_engine.run_ledger.start_run(
        session_id=failed_session_id,
        run_type="epic",
        run_name="failed",
        department="core",
        build_id="BUILD-2",
        summary={"phase": "prebuild"},
        artifacts={"run_identity": failed_artifacts["run_identity"]},
    )
    await real_engine.run_ledger.finalize_run(
        session_id=failed_session_id,
        status="failed",
        summary=failed_summary,
        artifacts=failed_artifacts,
    )

    client = _client()
    completed = client.get("/v1/cards/view?filter=completed", headers={"X-API-Key": "test-key"})
    terminal_failure = client.get("/v1/cards/view?filter=terminal_failure", headers={"X-API-Key": "test-key"})
    card_detail = client.get("/v1/cards/CARD-VERIFIED/view", headers={"X-API-Key": "test-key"})
    run_history = client.get("/v1/runs/view?limit=5", headers={"X-API-Key": "test-key"})
    run_detail = client.get(f"/v1/runs/{verified_session_id}/view", headers={"X-API-Key": "test-key"})

    assert completed.status_code == 200
    assert completed.json()["items"][0]["card_id"] == "CARD-VERIFIED"
    assert completed.json()["items"][0]["filter_bucket"] == "completed"
    assert completed.json()["items"][0]["last_run"]["lifecycle_category"] == "artifact_run_verified"

    assert terminal_failure.status_code == 200
    assert terminal_failure.json()["items"][0]["card_id"] == "CARD-FAILED"
    assert terminal_failure.json()["items"][0]["filter_bucket"] == "terminal_failure"

    assert card_detail.status_code == 200
    card_payload = card_detail.json()
    assert card_payload["execution_profile"] == "builder_guard_app_v1"
    assert card_payload["run"]["lifecycle_category"] == "artifact_run_verified"
    assert card_payload["run_action"]["endpoint"] == "/v1/system/run-active"
    assert card_payload["artifact_contract"]["primary_output"] == "agent_output/main.py"

    assert run_history.status_code == 200
    history_items = run_history.json()["items"]
    assert any(item["session_id"] == verified_session_id and item["lifecycle_category"] == "artifact_run_verified" for item in history_items)
    assert any(item["session_id"] == failed_session_id and item["lifecycle_category"] == "prebuild_blocked" for item in history_items)

    assert run_detail.status_code == 200
    run_payload = run_detail.json()
    assert run_payload["lifecycle_category"] == "artifact_run_verified"
    assert run_payload["verification"]["status"] == "verified"
    assert "agent_output/main.py" in run_payload["key_artifacts"]


def test_system_operator_views_surface_provider_and_health_status(monkeypatch) -> None:
    """Layer: integration. Verifies provider and system health operator views expose degraded-first status on the API."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    class _FakeSelector:
        def __init__(self, organization, preferences, user_settings) -> None:
            del organization, preferences, user_settings
            self._decision = {}

        def select(self, *, role: str) -> str:
            self._decision = {
                "selected_model": f"{role}-selected",
                "final_model": f"{role}-fallback",
                "demoted": True,
                "reason": "fallback_profile",
            }
            return f"{role}-selected"

        def get_last_selection_decision(self) -> dict[str, object]:
            return dict(self._decision)

        def get_dialect_name(self, final_model: str) -> str:
            return f"dialect:{final_model}"

    monkeypatch.setattr(api_module, "_discover_active_roles", lambda _root: ["coder"])
    monkeypatch.setattr(api_module, "load_user_preferences", lambda: {})
    monkeypatch.setattr(api_module, "load_user_settings", lambda: {})
    monkeypatch.setattr(api_module, "ModelSelector", _FakeSelector)

    client = _client()
    provider_response = client.get("/v1/system/provider-status", headers={"X-API-Key": "test-key"})
    health_response = client.get("/v1/system/health-view", headers={"X-API-Key": "test-key"})

    assert provider_response.status_code == 200
    provider_payload = provider_response.json()
    assert provider_payload["primary_status"] == "degraded"
    assert provider_payload["degraded"] is True
    assert provider_payload["assignments"][0]["role"] == "coder"

    assert health_response.status_code == 200
    health_payload = health_response.json()
    assert "primary_status" in health_payload
    assert "provider_status" in health_payload
    assert health_payload["provider_status"]["degraded"] is True
