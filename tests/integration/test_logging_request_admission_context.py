"""Integration: real application request admission owns logging and restores its caller."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext

import pytest

from orket.adapters.observability.logging_context import bind_logging, prepare_logging, selected_logging
from orket.application.services.extension_catalog_commands import list_installed_extensions
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.helpers.webhook import application

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _app(kind, root):
    return create_api_app(CompositionConfig(project_root=root)) if kind == "api" else application(root)


def _owner(app, kind):
    return getattr(app.state, "api_runtime_context" if kind == "api" else "webhook_runtime")


def _assert_closed(owner, kind):
    assert owner.closed and owner.active_request_count == 0 and owner.active_background_task_count == 0
    assert owner.engine._closed if kind == "api" else owner.client.is_closed


async def _invoke_success_and_failure(owner):
    seen = []
    failure = RuntimeError("request fixture failure")

    async def observe(fail):
        seen.append(selected_logging())
        assert owner.active_request_count == 1
        await asyncio.sleep(0)
        seen.append(selected_logging())
        if fail:
            raise failure

    await owner.run_request(lambda: observe(False))
    with pytest.raises(RuntimeError) as caught:
        await owner.run_request(lambda: observe(True))
    assert caught.value is failure
    assert len(seen) == 4 and all(value is owner.logging_context for value in seen)
    assert owner.active_request_count == 0


async def _invoke_cancelled(owner):
    entered, stopped = asyncio.Event(), asyncio.Event()
    seen = []

    async def hold():
        seen.append(selected_logging())
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            seen.append(selected_logging())
            stopped.set()

    task = asyncio.create_task(owner.run_request(hold))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert owner.active_request_count == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stopped.is_set() and owner.active_request_count == 0
        assert len(seen) == 2 and all(value is owner.logging_context for value in seen)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("kind", ["api", "webhook"])
@pytest.mark.parametrize("bind_caller", [False, True], ids=["inherited-caller", "explicit-caller"])
async def test_application_admission_binds_each_request_and_restores_caller(tmp_path, monkeypatch, kind, bind_caller):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    caller = await prepare_logging(LoggingInputs(tmp_path / "caller"))
    app = _app(kind, tmp_path / "runtime")
    async with app.router.lifespan_context(app):
        owner = _owner(app, kind)
        with bind_logging(caller) if bind_caller else nullcontext():
            before = selected_logging(required=False)
            await _invoke_success_and_failure(owner)
            assert selected_logging(required=False) is before
            await _invoke_cancelled(owner)
            assert selected_logging(required=False) is before
    _assert_closed(owner, kind)


@pytest.mark.parametrize("kind", ["api", "webhook"])
@pytest.mark.parametrize("bind_caller", [False, True], ids=["inherited-caller", "explicit-caller"])
async def test_refused_asgi_response_uses_restored_transport_caller(tmp_path, monkeypatch, kind, bind_caller):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    caller = await prepare_logging(LoggingInputs(tmp_path / "caller"))
    app = _app(kind, tmp_path / "runtime")
    messages, selections = [], []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)
        selections.append(selected_logging(required=False))

    scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method="GET", scheme="http",
                 path="/health", raw_path=b"/health", root_path="", query_string=b"", headers=[],
                 server=("test", 80), client=("test", 1))
    async with app.router.lifespan_context(app):
        owner = _owner(app, kind)
        await owner.close()
        _assert_closed(owner, kind)
        with bind_logging(caller) if bind_caller else nullcontext():
            before = selected_logging(required=False)
            await app(scope, receive, send)
            assert selected_logging(required=False) is before
    assert messages[0]["type"] == "http.response.start" and messages[0]["status"] == 503
    assert messages[-1]["type"] == "http.response.body"
    assert selections and all(value is before for value in selections)
    _assert_closed(owner, kind)


@pytest.mark.parametrize("fail", [False, True], ids=["normal", "failed-command"])
async def test_cli_context_prepares_real_extension_catalog_and_restores_same_task(tmp_path, fail):
    from orket.application.services.cli_application_context import open_cli_application

    caller = await prepare_logging(LoggingInputs(tmp_path / "caller"))
    inputs = RuntimeConstructionInputs(tmp_path, {"ORKET_DISABLE_SANDBOX": "1"}, "{}", "{}")
    failure = RuntimeError("CLI command fixture failure")
    observed = None
    with bind_logging(caller):
        try:
            async with open_cli_application(inputs) as manager:
                selected = selected_logging()
                assert selected is not caller and selected.inputs.invocation_root == tmp_path
                assert await list_installed_extensions(manager) == []
                if fail:
                    raise failure
        except RuntimeError as error:
            observed = error
        assert selected_logging() is caller
    assert observed is (failure if fail else None)
