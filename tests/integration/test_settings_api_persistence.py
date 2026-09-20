"""Actual API listener reads persisted settings and retains admitted file writes."""
# Layer: integration
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from orket import settings
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.integration.test_api_active_request_ownership import serving_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _application(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", "bt0-local-test-key")
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / ".orket/durable"))
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(tmp_path / "outward.db"))
    path = tmp_path / "user_settings.json"
    path.write_text('{"keep": 17, "protocol_timezone": "UTC"}', encoding="utf-8")
    settings.set_settings_file(path)
    settings.set_preferences_file(tmp_path / "preferences.json")
    settings.set_runtime_settings_context(user_settings={"protocol_timezone": "Pacific/Honolulu"}, user_preferences={})
    return create_api_app(CompositionConfig(project_root=tmp_path)), path


async def test_api_settings_read_and_patch_persistence_independently_of_runtime_snapshot(tmp_path, monkeypatch):
    app, path = _application(tmp_path, monkeypatch)
    async with serving_api(app) as client:
        before = await client.get("/v1/settings")
        assert before.status_code == 200
        assert before.json()["settings"]["protocol_timezone"]["value"] == "UTC"
        saved = await client.patch("/v1/settings", json={"protocol_timezone": "America/Denver"})
        assert saved.status_code == 200, saved.text
        after = await client.get("/v1/settings")
        assert after.json()["settings"]["protocol_timezone"]["value"] == "America/Denver"
    assert json.loads(path.read_text(encoding="utf-8")) == {"keep": 17, "protocol_timezone": "America/Denver"}
    assert settings.load_user_settings()["protocol_timezone"] == "Pacific/Honolulu"
    assert app.state.api_runtime_context.closed


async def test_api_shutdown_waits_for_admitted_settings_write(tmp_path, monkeypatch):
    app, path = _application(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    original = Path.replace

    def held_replace(source, target):
        if target == path:
            entered.set()
            assert release.wait(5)
        return original(source, target)

    monkeypatch.setattr(Path, "replace", held_replace)
    async with serving_api(app) as client:
        context = app.state.api_runtime_context
        request = asyncio.create_task(client.patch("/v1/settings", json={"protocol_timezone": "America/Denver"}))
        closing = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            heartbeat = await asyncio.wait_for(client.get("/v1/system/heartbeat"), 0.5)
            assert heartbeat.status_code == 200
            closing = asyncio.create_task(context.close())
            await asyncio.sleep(0.03)
            assert not closing.done() and context.active_request_count == 1
        finally:
            release.set()
            await asyncio.gather(request, *([closing] if closing is not None else []))
    assert context.closed
    assert json.loads(path.read_text(encoding="utf-8")) == {"keep": 17, "protocol_timezone": "America/Denver"}



@pytest.mark.parametrize("method, endpoint", [("PATCH", "/v1/settings"), ("POST", "/v1/system/runtime-policy")])
async def test_api_conflicting_updates_require_reload(tmp_path, monkeypatch, method, endpoint):
    import orket.interfaces.api as api

    app, path = _application(tmp_path, monkeypatch)
    read = api.load_user_settings_async
    first_read, both_read, release_second = asyncio.Event(), asyncio.Event(), asyncio.Event()
    observed = []

    async def hold_captured_read():
        value = await read()
        observed.append(value)
        if len(observed) == 1:
            first_read.set()
            await asyncio.wait_for(both_read.wait(), 5)
        elif len(observed) == 2:
            both_read.set()
            await asyncio.wait_for(release_second.wait(), 5)
        return value

    monkeypatch.setattr(api, "load_user_settings_async", hold_captured_read)
    async with serving_api(app) as client:
        first = asyncio.create_task(client.request(method, endpoint, json={"protocol_locale": "en_US.UTF-8"}))
        second = None
        try:
            assert await asyncio.wait_for(first_read.wait(), 3)
            second = asyncio.create_task(client.request(method, endpoint, json={"protocol_timezone": "America/Denver"}))
            one = await first
            assert one.status_code == 200, one.text
        finally:
            release_second.set()
            await asyncio.gather(first, *([second] if second is not None else []), return_exceptions=True)
        two = await second
        assert two.status_code == 409 and two.json()["detail"]["code"] == "settings_conflict"
        retained = json.loads(path.read_text(encoding="utf-8"))
        assert retained == {"keep": 17, "protocol_timezone": "UTC", "protocol_locale": "en_US.UTF-8"}
        retry = await client.request(method, endpoint, json={"protocol_timezone": "America/Denver"})
        assert retry.status_code == 200, retry.text
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "keep": 17, "protocol_timezone": "America/Denver", "protocol_locale": "en_US.UTF-8",
    }
    assert app.state.api_runtime_context.closed
