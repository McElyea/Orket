"""Integration: queued API construction preserves selected native roots and runtime policy."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx
import pytest

from orket.interfaces.api import create_api_app
from orket.settings import set_runtime_settings_context
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def captured_environment():
    return dict(os.environ, ORKET_API_KEY=TEST_API_KEY, ORKET_DURABLE_ROOT="state",
        ORKET_EXTENSIONS_CATALOG="catalog.json", ORKET_OUTBOUND_POLICY_CONFIG_PATH="outbound.json",
        ORKET_STATE_BACKEND_MODE="local", ORKET_RUN_LEDGER_MODE="sqlite",
        ORKET_GOVERNED_AGENT_CAPACITY_LIMIT="3", ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED="0",
        ORKET_GOVERNED_AGENT_PROVIDER_MODE="llama_cpp", ORKET_LLM_PROVIDER="llama_cpp",
        ORKET_LLAMA_CPP_BASE_URL="http://127.0.0.1:18765", ORKET_TTS_BACKEND="null",
        ORKET_GITEA_ARTIFACT_CACHE_ROOT="export-cache", ORKET_GITEA_ARTIFACT_BRANCH="captured",
        ORKET_ALLOWED_ORIGINS="http://captured.example", ORKET_DISABLE_SANDBOX="1")


async def assert_captured_runtime(app, root):
    owner = app.state.api_runtime_context
    engine, manager = owner.engine, owner.extension_manager
    assert engine.state_backend_mode == "local" and engine.run_ledger_mode == "sqlite"
    assert engine.runtime_context.user_settings["selected"] == {"value": "captured"}
    assert owner.project_root == root / "project"
    assert Path(engine.db_path) == root / "state/db/orket_persistence.db"
    assert manager.catalog_path == root / "catalog.json"
    assert manager.install_root == root / "state/extensions"
    assert engine._pipeline.artifact_exporter.binding()["branch"] == "captured"
    assert Path(engine._pipeline.artifact_exporter.binding()["cache_root"]) == root / "export-cache"
    assert owner.governed_agent_runtime.status()["capacity_limit"] == 3
    assert owner.governed_agent_runtime.status()["provider_mode"] == "llama_cpp"
    assert owner.extension_runtime_service._model_provider._provider.provider_name == "llama_cpp"
    assert owner.extension_runtime_service._model_provider._provider.openai_base_url == "http://127.0.0.1:18765/v1"
    assert type(owner.extension_runtime_service._tts_provider).__name__ == "NullTTSProvider"
    assert app.state.outbound_policy_config == {"policy_version": "captured"}
    assert await engine.cards.get_by_id("captured-probe") is None
    assert await owner.governed_agent_runtime.list_wakes() == ()
    assert await asyncio.to_thread(Path(engine.db_path).is_file)
    assert await asyncio.to_thread((root / "state/db/control_plane_records.sqlite3").is_file)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
        assert (await client.get("/v1/system/runtime-policy", headers={"X-API-Key": TEST_API_KEY})).status_code == 200
        assert (await client.get("/v1/system/runtime-policy", headers={"X-API-Key": "rotated"})).status_code == 403
        response = await client.options("/v1/system/runtime-policy", headers={
            "Origin": "http://captured.example", "Access-Control-Request-Method": "GET"})
        assert response.headers["access-control-allow-origin"] == "http://captured.example"


async def test_factory_captures_inputs_before_cwd_environment_and_settings_rotation(tmp_path, monkeypatch):
    original, rotated = tmp_path / "original", tmp_path / "rotated"
    (original / "project").mkdir(parents=True)
    rotated.mkdir()
    await asyncio.to_thread((original / "project/outbound.json").write_text,
                            '{"policy_version":"captured"}', encoding="utf-8")
    monkeypatch.chdir(original)
    environment = captured_environment()
    settings = {"selected": {"value": "captured"}}
    set_runtime_settings_context(user_settings=settings, user_preferences={"theme": "captured"})
    app = create_api_app(project_root=Path("project"), environment=environment)
    settings["selected"]["value"] = "caller-mutation"
    environment.update(ORKET_API_KEY="rotated", ORKET_TTS_BACKEND="unsupported",
                       ORKET_GOVERNED_AGENT_CAPACITY_LIMIT="99")
    monkeypatch.chdir(rotated)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("ORKET_RUN_LEDGER_MODE", "protocol")
    set_runtime_settings_context(user_settings={"selected": {"value": "rotated"}}, user_preferences={})
    async with app.router.lifespan_context(app):
        await assert_captured_runtime(app, original)
    assert app.state.api_runtime_context.closed
    assert list(rotated.iterdir()) == []
    assert app.state.api_preparation.inputs.user_preferences() == {"theme": "captured"}
