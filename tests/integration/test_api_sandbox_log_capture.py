"""Captured sandbox log invocation and explicit direct-call admission."""
import asyncio
import threading
from types import SimpleNamespace

import httpx
import pytest

from orket.interfaces.api import create_api_app
from tests.integration.test_api_sandbox_log_ownership import install_pipeline_probe

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_sandbox_log_invocation_is_captured_before_construction(tmp_path, monkeypatch):
    await asyncio.to_thread((tmp_path / "sandbox-log-input.txt").write_text, "owned", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            files=[], owners=[], cleanup=[], children=[], commands=[])
    invocation = {"method_name": "get_logs", "args": ["sandbox-test", "api"]}

    def mutate_after_admission():
        try:
            if state.entered.wait(5):
                invocation["args"][1] = "frontend"
        finally:
            state.release.set()

    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        context = app.state.api_runtime_context
        monkeypatch.setattr(context.api_runtime_node, "resolve_sandbox_logs_invocation", lambda *_: invocation)
        install_pipeline_probe(app, tmp_path, monkeypatch, state, "construction", "normal")
        mutation = threading.Thread(target=mutate_after_admission)
        mutation.start()
        try:
            response = await asyncio.wait_for(client.get("/v1/sandboxes/sandbox-test/logs?service=api"), 5)
            assert response.status_code == 200 and response.json() == {"logs": "native sandbox logs\n"}
            assert invocation["args"] == ["sandbox-test", "frontend"]
            assert len(state.commands) == 1 and state.commands[0][-1] == "api"
            assert all(owner._closed for owner in state.owners)
            assert not context.engine._pipeline._closed and context.active_request_count == 0
        finally:
            state.release.set()
            await asyncio.to_thread(mutation.join, 5)
            for close in state.cleanup:
                await close()
        assert not mutation.is_alive() and all(stream.closed for stream in state.files)
        assert all(child.returncode == 0 and child.stdin.closed and child.stdout.closed for child in state.children)


@pytest.mark.contract
async def test_sandbox_sync_log_read_refuses_event_loop_before_lookup(tmp_path, monkeypatch):
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app):
        sandbox = app.state.api_runtime_context.engine._pipeline.sandbox_orchestrator
        looked_up = []
        original = sandbox.lifecycle_repository.get_record

        async def lookup(identifier):
            looked_up.append(identifier)
            return await original(identifier)

        monkeypatch.setattr(sandbox.lifecycle_repository, "get_record", lookup)
        with pytest.raises(RuntimeError, match="E_SANDBOX_LOGS_REQUIRES_WORKER"):
            sandbox.get_logs("absent")
        assert looked_up == []


@pytest.mark.contract
@pytest.mark.parametrize("invocation", [
    {"method_name": 123}, {"method_name": "get_logs", "extra": "unadmitted"},
    {"method_name": "get_logs", "unsupported_detail": {"message": "unadmitted"}},
])
async def test_sandbox_malformed_invocation_refuses_before_construction(tmp_path, monkeypatch, invocation):
    app = create_api_app(project_root=tmp_path, environment={"ORKET_API_KEY": "fixture"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app, raise_app_exceptions=False),
        base_url="http://fixture", headers={"X-API-Key": "fixture"},
    ) as client:
        context = app.state.api_runtime_context
        monkeypatch.setattr(context.api_runtime_node, "resolve_sandbox_logs_invocation", lambda *_: invocation)
        constructed = []
        original = context.api_runtime_host.create_execution_pipeline

        def construct(workspace):
            owner = original(workspace)
            constructed.append(owner)
            return owner

        monkeypatch.setattr(context.api_runtime_host, "create_execution_pipeline", construct)
        try:
            assert (await client.get("/v1/sandboxes/absent/logs")).status_code == 500
            assert constructed == []
        finally:
            for owner in constructed:
                await owner.close()
