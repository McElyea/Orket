"""Layer: integration. Actual selection, files, API owners and controlled HTTP."""
import asyncio
import json
import os
import threading

import httpx
import pytest

from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.model_selection_service import ModelSelectionService
from orket.interfaces.api import create_api_app
from orket.settings import clear_runtime_settings_context, set_runtime_settings_context
from tests.helpers.odr_provider_server import AUDITOR, MODEL, provider_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _write_json(path, payload):
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")


def _environment(endpoint):
    return {**os.environ, "ORKET_API_KEY": "fixture-key", "ORKET_OPERATOR_MODEL": MODEL,
            "ORKET_LLM_PROVIDER": "openai_compat", "ORKET_LLM_OPENAI_BASE_URL": endpoint,
            "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false",
            "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false"}


async def test_default_selection_preserves_runtime_settings_context():
    set_runtime_settings_context(user_preferences={"models": {"coder": "candidate"}},
                                 user_settings={"model_compliance_policy": {
                                     "blocked_models": ["candidate"], "fallback_model": "fallback"}})
    try:
        prepared = await ModelSelectionService(environment={}).prepare()
        selected = prepared.select("coder")
        assert selected.selected_model == "candidate" and selected.final_model == "fallback"
    finally:
        clear_runtime_settings_context()


async def test_real_driver_uses_host_environment_and_closes_http_client(tmp_path, monkeypatch):
    with provider_server() as (endpoint, calls):
        environment = _environment(endpoint)
        host = ApiRuntimeHostService(tmp_path, environment=environment)
        environment["ORKET_OPERATOR_MODEL"] = "later"
        environment["ORKET_LLM_OPENAI_BASE_URL"] = "http://127.0.0.1:1/v1"
        monkeypatch.setenv("ORKET_OPERATOR_MODEL", "ambient-later")
        driver = await host.create_chat_driver()
        try:
            assert driver.provider.model == MODEL and driver.project_root == tmp_path
            reply = await driver.process_request("Explain the system to a curious developer.")
            assert AUDITOR.strip() in reply
            sent = [call[2] for call in calls if call[0] == "POST"]
            assert len(sent) == 1 and sent[0]["model"] == MODEL
        finally:
            await host.close_chat_driver(driver)
        assert driver.provider.client.is_closed


async def test_real_api_chat_closes_request_driver(tmp_path, monkeypatch):
    import orket.driver as driver_module

    created = []
    actual = driver_module.OrketDriver.__init__

    def observe(self, *args, **kwargs):
        actual(self, *args, **kwargs)
        created.append(self)

    monkeypatch.setattr(driver_module.OrketDriver, "__init__", observe)
    with provider_server() as (endpoint, calls):
        app = create_api_app(project_root=tmp_path, environment=_environment(endpoint))
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://fixture") as client:
                response = await client.post("/v1/system/chat-driver", headers={"X-API-Key": "fixture-key"},
                                             json={"message": "Explain the system to a curious developer."})
            assert response.status_code == 200 and AUDITOR.strip() in response.json()["response"]
            assert len(created) == 1 and created[0].provider.client.is_closed
            assert len([c for c in calls if c[0] == "POST"]) == 1


async def test_cancelled_driver_bootstrap_drains_worker_and_closes_actual_transport(tmp_path, monkeypatch):
    import orket.driver as driver_module

    started, release = threading.Event(), threading.Event()
    created, worker_threads = [], []
    actual = driver_module.OrketDriver.__init__

    def held(self, *args, **kwargs):
        actual(self, *args, **kwargs)
        created.append(self)
        worker_threads.append(threading.get_ident())
        started.set()
        assert release.wait(10)

    monkeypatch.setattr(driver_module.OrketDriver, "__init__", held)
    host = ApiRuntimeHostService(tmp_path, environment=_environment("http://127.0.0.1:1/v1"))
    task = asyncio.create_task(host.create_chat_driver())
    try:
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.wait_for(asyncio.sleep(0.02), 0.5)
        assert not task.done() and not created[0].provider.client.is_closed
        assert worker_threads[0] != threading.get_ident()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert created[0].provider.client.is_closed


async def test_api_model_assignments_report_actual_score_provenance(tmp_path):
    score = tmp_path / "scores.json"
    await _write_json(score, {"model_compliance": {"candidate": {"compliance_score": 10}}})
    await _write_json(tmp_path / "model/organization.json", {
        "name": "Fixture", "vision": "Preview", "ethos": "Truth",
        "process_rules": {"model_compliance_policy": {
            "min_score": 85, "fallback_model": "qwen-fallback", "score_source": str(score)}}})
    app = create_api_app(project_root=tmp_path, environment={**os.environ, "ORKET_API_KEY": "key", "ORKET_MODEL_CODER": "candidate"})
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://fixture",
    ) as client:
        first = await client.get("/v1/system/model-assignments?roles=coder", headers={"X-API-Key": "key"})
        assert first.status_code == 200
        item = first.json()["items"][0]
        assert item["selected_model"] == "candidate" and item["final_model"] == "qwen-fallback"
        assert item["reason"] == "score_below_threshold" and item["score_source"]["status"] == "observed"
        await asyncio.to_thread(score.unlink)
        second = await client.get("/v1/system/model-assignments?roles=coder", headers={"X-API-Key": "key"})
        item = second.json()["items"][0]
        assert item["final_model"] == "candidate" and item["reason"] == "score_missing"
        assert item["score_source"]["status"] == "missing"


async def test_real_preview_uses_asset_model_and_project_files(tmp_path, monkeypatch):
    await _write_json(tmp_path / "model/organization.json", {"name": "Fixture", "vision": "Preview", "ethos": "Truth"})
    await _write_json(tmp_path / "model/core/epics/fixture.json", {
        "id": "EPIC", "name": "Fixture", "team": "fixture", "environment": "standard",
        "params": {"model_overrides": {"coder": "qwen2.5-fixture"}},
        "issues": [{"id": "ISSUE", "name": "Implement fixture", "seat": "coder"}]})
    await _write_json(tmp_path / "model/core/teams/fixture.json", {
        "name": "Fixture", "seats": {"coder": {"name": "coder", "roles": ["coder"]}}})
    await _write_json(tmp_path / "model/core/roles/coder.json", {
        "id": "ROLE", "name": "coder", "description": "Fixture role", "intent": "project-role-marker",
        "responsibilities": [], "tools": []})
    await _write_json(tmp_path / "model/core/dialects/qwen.json", {
        "model_family": "qwen", "dsl_format": "JSON", "hallucination_guard": "Fixture", "constraints": ["asset-model-dialect-marker"]})
    host = ApiRuntimeHostService(tmp_path, environment={"ORKET_MODEL_CODER": "llama-lower-priority"})
    builder = await host.create_preview_builder()
    monkeypatch.setenv("ORKET_MODEL_CODER", "ambient-later")
    preview = await builder.build_issue_preview("ISSUE", "fixture")
    assert preview["id"] == "ISSUE"
    assert "project-role-marker" in preview["compiled_system_prompt"]
    assert "asset-model-dialect-marker" in preview["compiled_system_prompt"]
