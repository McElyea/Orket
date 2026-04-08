import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

import orket.interfaces.api as api_module
import orket.marshaller.cli as marshaller_cli
from orket.streaming import CommitOrchestrator, InteractionManager, StreamBus

client = None


def test_interaction_websocket_requires_api_key(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws/interactions/no-session"):
        pass


def test_interaction_stream_flow_emits_commit_final(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    with client.websocket_connect(f"/ws/interactions/{session_id}?api_key=test-key") as ws:
        turn = client.post(
            f"/v1/interactions/{session_id}/turns",
            headers={"X-API-Key": "test-key"},
            json={"workload_id": "stream_test_v1", "input_config": {"seed": 123, "mode": "basic"}},
        )
        assert turn.status_code == 200
        events = [ws.receive_json() for _ in range(7)]
        event_types = [item["event_type"] for item in events]
        assert "turn_accepted" in event_types
        assert "turn_final" in event_types
        assert "commit_final" in event_types


def test_interaction_session_start_registers_runtime_surface(monkeypatch):
    """Layer: integration. Verifies the API start path records interaction-session ownership in GlobalState's transport registry."""
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )

    assert start.status_code == 200
    session_id = start.json()["session_id"]
    assert asyncio.run(api_module.runtime_state.is_interaction_session(session_id)) is True


def test_interaction_model_stream_flow_emits_commit_final(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "stub")

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    with client.websocket_connect(f"/ws/interactions/{session_id}?api_key=test-key") as ws:
        turn = client.post(
            f"/v1/interactions/{session_id}/turns",
            headers={"X-API-Key": "test-key"},
            json={"workload_id": "model_stream_v1", "input_config": {"seed": 123, "mode": "basic"}},
        )
        assert turn.status_code == 200
        events = [ws.receive_json() for _ in range(7)]
        event_types = [item["event_type"] for item in events]
        assert "turn_accepted" in event_types
        assert "model_selected" in event_types
        assert "model_loading" in event_types
        assert "model_ready" in event_types
        assert "token_delta" in event_types
        assert "turn_final" in event_types
        assert "commit_final" in event_types


def test_interaction_turn_unknown_workload_fails_clearly(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={"workload_id": "unknown_workload_v1", "input_config": {"seed": 1}},
    )
    assert turn.status_code == 400
    assert "Unknown workload 'unknown_workload_v1'" in turn.text
    assert "model_stream_v1" in turn.text


def test_interaction_model_stream_invalid_provider_mode_fails_fast(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "invalid")

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={"workload_id": "model_stream_v1", "input_config": {"seed": 1}},
    )
    assert turn.status_code == 400
    assert "Unsupported ORKET_MODEL_STREAM_PROVIDER='invalid'" in turn.text


def test_interaction_model_stream_preflight_runtime_error_maps_to_503(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")

    def _raise_runtime_error(*, workload_id, input_config, turn_params):
        raise RuntimeError("Real model provider unavailable.")

    monkeypatch.setattr(api_module, "validate_builtin_workload_start", _raise_runtime_error)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={"workload_id": "model_stream_v1", "input_config": {"seed": 1}},
    )
    assert turn.status_code == 503
    assert "Real model provider unavailable." in turn.text


def test_builtin_hint_request_cancel_turn_emits_turn_interrupted(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def _hints_cancel(*, workload_id, input_config, turn_params, interaction_context):
        return {"request_cancel_turn": 1, "post_finalize_wait_ms": 0}

    monkeypatch.setattr(api_module, "run_builtin_workload", _hints_cancel)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    with client.websocket_connect(f"/ws/interactions/{session_id}?api_key=test-key") as ws:
        turn = client.post(
            f"/v1/interactions/{session_id}/turns",
            headers={"X-API-Key": "test-key"},
            json={"workload_id": "stream_test_v1", "input_config": {"seed": 123, "mode": "basic"}},
        )
        assert turn.status_code == 200
        events = [ws.receive_json() for _ in range(3)]
        event_types = [item["event_type"] for item in events]
        assert "turn_accepted" in event_types
        assert "turn_interrupted" in event_types
        assert "commit_final" in event_types
        assert "turn_final" not in event_types


def test_interaction_builtin_turn_exposes_bounded_packet1_context(monkeypatch, tmp_path):
    """Layer: integration. Verifies built-in interaction turns expose the canonical packet1 session-context envelope."""
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module,
        "interaction_manager",
        InteractionManager(
            bus=StreamBus(),
            commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
            project_root=tmp_path,
        ),
        raising=False,
    )

    captured = {}
    captured_envelope = {}
    captured_lineage = []

    async def _capture_context(*, workload_id, input_config, turn_params, interaction_context):
        _ = (workload_id, input_config, turn_params)
        captured.update(interaction_context.packet1_context())
        captured_envelope.update(interaction_context.packet1_context_envelope())
        captured_lineage.extend(interaction_context.packet1_provider_lineage())
        return {"post_finalize_wait_ms": 0}

    monkeypatch.setattr(api_module, "run_builtin_workload", _capture_context)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper", "tone": "calm"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={
            "workload_id": "stream_test_v1",
            "input_config": {"seed": 321, "mode": "basic"},
            "department": "core",
            "workspace": "workspace/default",
            "turn_params": {"persona": "guard"},
        },
    )
    assert turn.status_code == 200

    for _ in range(20):
        if captured:
            break
        asyncio.run(asyncio.sleep(0.01))

    assert captured == {
        "session_params": {"npc": "innkeeper", "tone": "calm"},
        "input_config": {"seed": 321, "mode": "basic"},
        "turn_params": {"persona": "guard"},
        "workload_id": "stream_test_v1",
        "department": "core",
        "workspace": str((api_module._project_root() / "workspace" / "default").resolve()),
    }
    assert captured_envelope["context_version"] == "packet1_session_context_v1"
    assert captured_envelope["continuity"] == {
        "session_id": session_id,
        "session_params": {"npc": "innkeeper", "tone": "calm"},
    }
    assert captured_envelope["turn_request"] == {
        "input_config": {"seed": 321, "mode": "basic"},
        "turn_params": {"persona": "guard"},
        "workload_id": "stream_test_v1",
        "department": "core",
        "workspace": str((api_module._project_root() / "workspace" / "default").resolve()),
    }
    assert [row["provider_id"] for row in captured_lineage] == [
        "host_continuity",
        "turn_request",
        "extension_manifest_required_capabilities",
    ]
    assert captured_lineage[-1]["present"] is False


def test_interaction_extension_turn_includes_manifest_required_capabilities(monkeypatch, tmp_path):
    """Layer: integration. Verifies extension interaction turns preserve host-resolved capability metadata in the canonical envelope."""
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module,
        "interaction_manager",
        InteractionManager(
            bus=StreamBus(),
            commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
            project_root=tmp_path,
        ),
        raising=False,
    )

    captured = {}
    captured_envelope = {}
    captured_lineage = []

    class _FakeExtensionManager:
        def has_manifest_entry(self, workload_id: str) -> bool:
            return workload_id == "ext-workload"

        def required_capabilities_for_workload(self, workload_id: str) -> tuple[str, ...]:
            if workload_id != "ext-workload":
                raise ValueError(f"Unknown workload '{workload_id}'")
            return ("workspace.root", "clock.now")

        async def run_workload(
            self,
            *,
            workload_id: str,
            input_config: dict[str, object],
            workspace,
            department: str,
            interaction_context,
        ) -> None:
            _ = (workload_id, input_config, workspace, department)
            captured.update(interaction_context.packet1_context())
            captured_envelope.update(interaction_context.packet1_context_envelope())
            captured_lineage.extend(interaction_context.packet1_provider_lineage())

    monkeypatch.setattr(api_module, "extension_manager", _FakeExtensionManager(), raising=False)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={
            "workload_id": "ext-workload",
            "input_config": {"seed": 9},
            "department": "operations",
            "workspace": "workspace/default",
            "turn_params": {"mode": "extension"},
        },
    )
    assert turn.status_code == 200

    for _ in range(20):
        if captured:
            break
        asyncio.run(asyncio.sleep(0.01))

    assert captured == {
        "session_params": {"npc": "innkeeper"},
        "input_config": {"seed": 9},
        "turn_params": {"mode": "extension"},
        "workload_id": "ext-workload",
        "department": "operations",
        "workspace": str((api_module._project_root() / "workspace" / "default").resolve()),
        "required_capabilities": ["workspace.root", "clock.now"],
    }
    assert captured_envelope["context_version"] == "packet1_session_context_v1"
    assert captured_envelope["extension_manifest"] == {
        "required_capabilities": ["workspace.root", "clock.now"],
    }
    assert [row["provider_id"] for row in captured_lineage] == [
        "host_continuity",
        "turn_request",
        "extension_manifest_required_capabilities",
    ]
    assert captured_lineage[-1]["present"] is True


def test_interaction_session_inspection_surfaces_expose_context_lineage(monkeypatch, tmp_path):
    """Layer: integration. Verifies interaction sessions use existing session inspection routes to expose context lineage truthfully."""
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module,
        "interaction_manager",
        InteractionManager(
            bus=StreamBus(),
            commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
            project_root=tmp_path,
        ),
        raising=False,
    )

    async def _capture_context(*, workload_id, input_config, turn_params, interaction_context):
        _ = (workload_id, input_config, turn_params, interaction_context)
        return {"post_finalize_wait_ms": 0}

    monkeypatch.setattr(api_module, "run_builtin_workload", _capture_context)

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper", "tone": "calm"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/v1/interactions/{session_id}/turns",
        headers={"X-API-Key": "test-key"},
        json={
            "workload_id": "stream_test_v1",
            "input_config": {"seed": 111, "mode": "basic"},
            "department": "core",
            "workspace": "workspace/default",
            "turn_params": {"persona": "guard"},
        },
    )
    assert turn.status_code == 200

    detail = client.get(f"/v1/sessions/{session_id}", headers={"X-API-Key": "test-key"})
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["surface"] == "interaction_session"
    assert detail_payload["continuity_identifier"] == "session_id"
    assert detail_payload["inspection_only"] is True
    assert detail_payload["turn_count"] == 1

    status = client.get(f"/v1/sessions/{session_id}/status", headers={"X-API-Key": "test-key"})
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["surface"] == "interaction_session"
    assert status_payload["summary"]["context_version"] == "packet1_session_context_v1"
    assert status_payload["summary"]["continuity_identifier"] == "session_id"
    assert status_payload["artifacts"]["targeted_replay"] == "run_session_only"

    snapshot = client.get(f"/v1/sessions/{session_id}/snapshot", headers={"X-API-Key": "test-key"})
    assert snapshot.status_code == 200
    snapshot_payload = snapshot.json()
    assert snapshot_payload["snapshot_kind"] == "interaction_session_context"
    assert snapshot_payload["session_context_pipeline"]["context_version"] == "packet1_session_context_v1"
    assert [row["provider_id"] for row in snapshot_payload["session_context_pipeline"]["provider_lineage"]] == [
        "host_continuity",
        "turn_request",
        "extension_manifest_required_capabilities",
    ]
    assert snapshot_payload["session_context_pipeline"]["latest_context_envelope"]["continuity"] == {
        "session_id": session_id,
        "session_params": {"npc": "innkeeper", "tone": "calm"},
    }
    assert snapshot_payload["session_context_pipeline"]["latest_context_envelope"]["turn_request"] == {
        "input_config": {"seed": 111, "mode": "basic"},
        "turn_params": {"persona": "guard"},
        "workload_id": "stream_test_v1",
        "department": "core",
        "workspace": str((api_module._project_root() / "workspace" / "default").resolve()),
    }
    assert snapshot_payload["replay_boundary"]["timeline_view"] == "inspection_only"
    assert snapshot_payload["replay_boundary"]["targeted_replay"] == "run_session_only"

    replay = client.get(f"/v1/sessions/{session_id}/replay", headers={"X-API-Key": "test-key"})
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload["surface"] == "interaction_session"
    assert replay_payload["inspection_only"] is True
    assert replay_payload["turn_count"] == 1
    assert replay_payload["turns"][0]["turn_index"] == 1
    assert replay_payload["turns"][0]["context_version"] == "packet1_session_context_v1"
    assert replay_payload["turns"][0]["context_envelope"]["turn_request"]["workload_id"] == "stream_test_v1"


def test_interaction_session_targeted_replay_fails_closed(monkeypatch, tmp_path):
    """Layer: integration. Verifies targeted replay stays run-oriented and rejects interaction sessions."""
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setattr(
        api_module,
        "interaction_manager",
        InteractionManager(
            bus=StreamBus(),
            commit_orchestrator=CommitOrchestrator(project_root=tmp_path),
            project_root=tmp_path,
        ),
        raising=False,
    )

    start = client.post(
        "/v1/interactions/sessions",
        headers={"X-API-Key": "test-key"},
        json={"session_params": {"npc": "innkeeper"}},
    )
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    response = client.get(
        f"/v1/sessions/{session_id}/replay?issue_id=ISS-1&turn_index=1",
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Targeted replay is not supported for interaction sessions."


def test_marshaller_runs_endpoint_returns_rows(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def _fake_list(_workspace_root, *, limit: int = 20):
        return [{"run_id": "run-1", "attempt_count": 2, "accepted": True, "accepted_attempt_index": 2}]

    monkeypatch.setattr(marshaller_cli, "list_marshaller_runs", _fake_list)
    response = client.get("/v1/marshaller/runs?limit=5", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "run-1"


def test_marshaller_run_inspect_maps_missing_to_404(monkeypatch):
    monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    async def _fake_inspect(_workspace_root, *, run_id: str, attempt_index=None):
        raise ValueError(f"Run not found: {run_id}")

    monkeypatch.setattr(marshaller_cli, "inspect_marshaller_attempt", _fake_inspect)
    response = client.get("/v1/marshaller/runs/missing-run", headers={"X-API-Key": "test-key"})
    assert response.status_code == 404
    assert "Run not found: missing-run" in response.text
