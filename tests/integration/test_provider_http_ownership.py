"""Layer: integration. Owned real TLS/client setup, network effects and interruption."""
import asyncio
import ssl
import threading

import httpx
import pytest

from orket.adapters.llm.provider_catalog_client import build_provider_catalog_client
from orket.application.services import provider_http_service as service
from orket.core.contracts.provider_http import ProviderHttpInputs
from orket.runtime.config.provider_runtime_target import list_provider_models
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.observed_http_server import observed_http_server
from tests.integration.test_provider_http_environment import _catalog

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_resources(monkeypatch):
    resources, closed = [], []
    original = service.build_provider_catalog_client

    def build(**options):
        owner = options.pop("own_resource")

        def own(resource):
            owner(resource)
            resources.append(resource)
            close = resource.aclose

            async def observed_close():
                await close()
                closed.append(resource)

            monkeypatch.setattr(resource, "aclose", observed_close)

        return original(**options, own_resource=own)

    monkeypatch.setattr(service, "build_provider_catalog_client", build)
    return resources, closed


@pytest.mark.parametrize("interrupt", ["cancel", "repeated", "timeout"])
@pytest.mark.parametrize("fail", [False, True], ids=["constructed", "native-failure"])
async def test_catalog_retains_native_tls_construction_and_outcome(tmp_path, monkeypatch, record_property, interrupt, fail):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    worker = []
    original = ssl.SSLContext.load_verify_locations
    resources, closed = observe_resources(monkeypatch)

    def held(context, *args, **options):
        worker.append(threading.get_ident())
        entered.set()
        try:
            assert release.wait(5), "native trust read escaped its owner"
            if fail:
                options["cafile"] = str(tmp_path / "missing-trust.pem")
            return original(context, *args, **options)
        finally:
            finished.set()

    monkeypatch.setattr(ssl.SSLContext, "load_verify_locations", held)
    timeout = asyncio.timeout(None)
    async with observed_http_server(_catalog("ollama", "unused")) as server:
        async def invoke():
            async with timeout:
                return await list_provider_models(provider="ollama", base_url=server[0], timeout_s=2, environment={})

        task = asyncio.create_task(invoke())
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            assert len(worker) == 1 and worker[0] != threading.get_ident()
            await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
            if interrupt == "timeout":
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
            await asyncio.sleep(.03)
            if interrupt == "repeated":
                task.cancel()
                await asyncio.sleep(.01)
            assert not task.done() and not finished.is_set() and not server[1]
            release.set()
            expected = FileNotFoundError if fail else (TimeoutError if interrupt == "timeout" else asyncio.CancelledError)
            with pytest.raises(expected):
                await asyncio.wait_for(asyncio.shield(task), 5)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert finished.is_set() and not server[1]
        assert resources == [] if fail else len(resources) == 2
        assert all(resource in closed for resource in resources)
        assert all(resource.is_closed for resource in resources if isinstance(resource, httpx.AsyncClient))


@pytest.mark.parametrize("interrupt", ["cancel", "repeated", "timeout"])
@pytest.mark.parametrize("failure", [False, True], ids=["clean-close", "close-failure"])
@pytest.mark.parametrize("request_failure", [False, True], ids=["response-ok", "http-error"])
async def test_catalog_close_remains_owned_after_success_or_failure(monkeypatch, interrupt, failure, request_failure):
    arrived, release = asyncio.Event(), asyncio.Event()
    resources, closed = observe_resources(monkeypatch)
    original = httpx.AsyncClient.aclose
    errors = []

    async def held(client):
        arrived.set()
        await asyncio.wait_for(release.wait(), 5)
        await original(client)
        if failure:
            error = OSError("controlled close failure after actual close")
            errors.append(error)
            raise error

    monkeypatch.setattr(httpx.AsyncClient, "aclose", held)
    timeout = asyncio.timeout(None)

    async def respond(request):
        return (503 if request_failure else 200), {"models": [{"name": "observed"}]}

    async with observed_http_server(respond) as server:
        async def invoke():
            async with timeout:
                return await list_provider_models(provider="ollama", base_url=server[0], timeout_s=2, environment={})

        task = asyncio.create_task(invoke())
        try:
            await asyncio.wait_for(arrived.wait(), 5)
            if interrupt == "timeout":
                timeout.reschedule(asyncio.get_running_loop().time() + .01)
            else:
                task.cancel()
            await asyncio.sleep(.03)
            if interrupt == "repeated":
                task.cancel()
                await asyncio.sleep(.01)
            assert len(server[1]) == 1 and not task.done()
            release.set()
            expected = BaseExceptionGroup if failure else (httpx.HTTPStatusError if request_failure else (
                TimeoutError if interrupt == "timeout" else asyncio.CancelledError))
            with pytest.raises(expected) as outcome:
                await asyncio.wait_for(asyncio.shield(task), 5)
            if failure:
                if request_failure:
                    assert isinstance(outcome.value.exceptions[0], httpx.HTTPStatusError)
                    assert outcome.value.exceptions[1].exceptions == tuple(errors)
                else:
                    assert outcome.value.exceptions == tuple(errors)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        assert len(resources) == 2 and resources[-1].is_closed
        assert resources[0] in closed


@pytest.mark.parametrize("mode", ["success", "http-error", "cancel", "timeout"])
async def test_catalog_request_outcome_closes_actual_client_and_network_handlers(monkeypatch, mode):
    arrived, release = asyncio.Event(), asyncio.Event()
    resources, closed = observe_resources(monkeypatch)

    async def respond(request):
        arrived.set()
        if mode in {"cancel", "timeout"}:
            await asyncio.wait_for(release.wait(), 5)
        return (503 if mode == "http-error" else 200), {"models": [{"name": "observed"}]}

    async with observed_http_server(respond, allow_disconnect=True) as server:
        task = asyncio.create_task(list_provider_models(provider="ollama", base_url=server[0], timeout_s=1, environment={}))
        try:
            await asyncio.wait_for(arrived.wait(), 5)
            if mode == "cancel":
                task.cancel()
            if mode == "success":
                assert (await task)["models"] == ["observed"]
            else:
                expected = {"http-error": httpx.HTTPStatusError, "cancel": asyncio.CancelledError,
                            "timeout": httpx.ReadTimeout}[mode]
                with pytest.raises(expected):
                    await asyncio.wait_for(asyncio.shield(task), 3)
            assert len(server[1]) == 1 and len(resources) == 2
            assert all(resource in closed for resource in resources) and resources[-1].is_closed
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_partial_proxy_construction_closes_already_acquired_transport(monkeypatch):
    resources, closed = observe_resources(monkeypatch)
    async with observed_http_server(_catalog("ollama", "unused")) as server:
        with pytest.raises(ValueError, match="E_PROVIDER_HTTP_PROXY_INVALID"):
            await list_provider_models(provider="ollama", base_url=server[0], timeout_s=1,
                environment={"HTTP_PROXY": server[0], "HTTPS_PROXY": "invalid://fixture-user:fixture-secret@proxy"})
        assert len(resources) == 1 and resources == closed and not server[1]


@pytest.mark.parametrize("budget", [float("inf"), float("-inf"), float("nan")])
async def test_nonfinite_budget_refuses_before_client_or_network_admission(monkeypatch, budget):
    resources, closed = observe_resources(monkeypatch)
    async with observed_http_server(_catalog("ollama", "unused")) as server:
        with pytest.raises(ValueError, match="E_PROVIDER_HTTP_TIMEOUT_NOT_FINITE"):
            await list_provider_models(provider="ollama", base_url=server[0], timeout_s=budget, environment={})
        assert not resources and not closed and not server[1]


async def test_native_constructor_refuses_event_loop_before_tls_keylog_file(tmp_path):
    keylog = tmp_path / "must-not-exist.log"
    with pytest.raises(RuntimeError, match="E_PROVIDER_HTTP_REQUIRES_ASYNC_OWNER"):
        build_provider_catalog_client(inputs=ProviderHttpInputs((), keylog_file=keylog),
            base_url="http://127.0.0.1:1", timeout_s=1, api_key=None, own_resource=lambda _: None)
    assert not await asyncio.to_thread(keylog.exists)
