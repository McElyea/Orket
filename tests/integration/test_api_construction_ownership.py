"""Integration: API transport stays closed until owned native preparation succeeds."""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import httpx
import pytest

from orket.interfaces.api_runtime_context import get_api_runtime_context
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_factory_defers_native_construction_and_requests_require_lifespan(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    target = tmp_path / ".orket/durable/db"
    entered = []
    original = Path.mkdir
    loop_thread = threading.get_ident()

    def observed(path, *args, **kwargs):
        if path == target:
            entered.append(threading.get_ident())
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", observed)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    assert get_api_runtime_context(app) is None and entered == []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api.test") as client:
        assert (await client.get("/health")).status_code == 503
        async with app.router.lifespan_context(app):
            owner = get_api_runtime_context(app)
            assert owner is not None and app.state.api_ready
            assert entered and loop_thread not in entered
            assert (await client.get("/health")).status_code == 200
            assert await owner.engine.cards.get_by_id("absent-construction-probe") is None
            assert await asyncio.to_thread(Path(owner.engine.db_path).is_file)
        assert owner.closed and not app.state.api_ready
        assert (await client.get("/health")).status_code == 503
    with pytest.raises(RuntimeError, match="E_API_RESTART_REQUIRES_NEW_APP"):
        async with app.router.lifespan_context(app):
            pytest.fail("A closed application must not acquire another runtime")


async def test_websocket_is_closed_before_acceptance_without_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    messages = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        messages.append(message)

    scope = {"type": "websocket", "path": "/ws/events", "root_path": "", "scheme": "ws",
             "query_string": b"", "headers": [(b"x-api-key", TEST_API_KEY.encode())],
             "server": ("test", 80), "client": ("test", 1), "subprotocols": [],
             "asgi": {"version": "3.0", "spec_version": "2.3"}}
    await app(scope, receive, send)
    assert messages == [{"type": "websocket.close", "code": 1001}]
    assert get_api_runtime_context(app) is None


async def test_schema_and_included_routes_are_prepared_off_loop_before_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    prepare, calls, loop_thread = app.openapi, [], threading.get_ident()

    def observe_schema():
        calls.append((threading.get_ident(), app.state.api_ready))
        return prepare()

    monkeypatch.setattr(app, "openapi", observe_schema)
    assert app.openapi_schema is None
    async with app.router.lifespan_context(app):
        assert len(calls) == 1 and calls[0][0] != loop_thread and calls[0][1] is False
        assert "/v1/sessions/{session_id}/replay" in app.openapi_schema["paths"]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
            # The first request exercises a real included router, including authentication.
            assert (await client.get("/v1/sessions/absent/replay", headers={"X-API-Key": TEST_API_KEY})).status_code == 404
            response = await client.get("/openapi.json")
            assert response.status_code == 200 and response.json() == app.openapi_schema
    assert app.state.api_runtime_context.closed
