"""Layer: integration. Real origin/proxy TCP observers distinguish captured network inputs."""
import asyncio
import threading

import pytest

from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config.provider_runtime_target import list_provider_models
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _catalog(provider, model):
    async def respond(request):
        assert request[0].startswith("GET ") and request[1] is None
        return 200, ({"data": [{"id": model}]} if provider == "openai_compat" else {"models": [{"name": model}]})

    return respond


def _ambient_proxy(monkeypatch, url):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setenv("HTTP_PROXY", url)
    monkeypatch.setenv("NO_PROXY", "")


@pytest.mark.parametrize("provider", ["openai_compat", "ollama"])
@pytest.mark.parametrize("mode", ["empty", "proxy", "bypass", "ambient"])
async def test_catalog_http_uses_supplied_environment_without_ambient_proxy_fallback(monkeypatch, provider, mode):
    async with (
        observed_http_server(_catalog(provider, "origin")) as origin,
        observed_http_server(_catalog(provider, "supplied")) as supplied,
        observed_http_server(_catalog(provider, "ambient")) as ambient,
    ):
        _ambient_proxy(monkeypatch, ambient[0])
        environment = None if mode == "ambient" else {}
        if mode in {"proxy", "bypass"}:
            environment = {"HTTP_PROXY": supplied[0], "NO_PROXY": "127.0.0.1" if mode == "bypass" else ""}
        result = await asyncio.wait_for(list_provider_models(
            provider=provider, base_url=origin[0], timeout_s=2, environment=environment), 5)
        expected = "ambient" if mode == "ambient" else ("supplied" if mode == "proxy" else "origin")
        observations = dict(models=result["models"], origin=len(origin[1]), supplied=len(supplied[1]), ambient=len(ambient[1]))
        assert observations == dict(models=[expected], origin=int(expected == "origin"),
                                    supplied=int(expected == "supplied"), ambient=int(expected == "ambient"))
        selected = dict(origin=origin, supplied=supplied, ambient=ambient)[expected]
        path = "/models" if provider == "openai_compat" else "/api/tags"
        target = path if expected == "origin" else origin[0] + path
        assert selected[1] == [(f"GET {target} HTTP/1.1", None)]


@pytest.mark.parametrize("provider", ["openai_compat", "ollama"])
async def test_direct_sync_catalog_captures_before_coroutine_bridge(monkeypatch, provider):
    entered, release = threading.Event(), threading.Event()
    original = inventory._run_coro_sync

    def held(coroutine):
        entered.set()
        if not release.wait(5):
            coroutine.close()
            raise AssertionError("catalog bridge release missed")
        return original(coroutine)

    monkeypatch.setattr(inventory, "_run_coro_sync", held)
    async with (observed_http_server(_catalog(provider, "captured")) as captured,
                observed_http_server(_catalog(provider, "changed")) as changed):
        _ambient_proxy(monkeypatch, captured[0])
        options = dict(base_url="http://unresolved-catalog.invalid", timeout_s=2)
        call = inventory.list_ollama_models_sync
        if provider == "openai_compat":
            call = inventory.list_openai_compat_models_sync
            options["api_key"] = None
        task = asyncio.create_task(asyncio.to_thread(call, **options))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            _ambient_proxy(monkeypatch, changed[0])
            release.set()
            assert await asyncio.wait_for(asyncio.shield(task), 5) == ["captured"]
            assert len(captured[1]) == 1 and not changed[1]
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
