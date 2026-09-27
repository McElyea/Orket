"""Actual standard-handler barriers for API startup native ownership controls."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextvars import ContextVar
from types import SimpleNamespace

import httpx

from orket.application.services import api_startup_service
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.logging import event_subscriber_count
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime import CompositionConfig
from tests.helpers.outward_authorization import TEST_API_KEY

STARTUP_CONTEXT = ContextVar("api_startup_diagnostic_context", default="unbound")


class HeldStartupHandler(logging.Handler):
    def __init__(self, event, *, failure=None):
        super().__init__()
        self.event, self.failure = event, failure
        self.entered, self.unblock, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.thread, self.started, self.context, self.record = None, None, None, None
        self.expired = False

    def emit(self, record):
        if record.getMessage() != self.event:
            return
        self.thread, self.started = threading.get_ident(), time.perf_counter()
        self.context, self.record = STARTUP_CONTEXT.get(), record
        self.entered.set()
        try:
            self.expired = not self.unblock.wait(2)
            if self.failure is not None:
                raise self.failure
        finally:
            self.finished.set()


def prepare_app(tmp_path, monkeypatch, *, warning, environment="local", failure=None):
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_ENV", environment)
    monkeypatch.setenv("ORKET_API_SECURITY_PROFILE", "local")
    monkeypatch.setenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "1" if warning == "bypass" else "0")
    monkeypatch.setenv("ORKET_GITEA_ALLOW_INSECURE", "1" if warning == "tls" else "0")
    monkeypatch.setenv("GITEA_URL", "https://gitea.invalid")
    app = create_api_app(CompositionConfig(project_root=tmp_path))
    name = "orket_insecure_no_api_key_enabled" if warning == "bypass" else "orket_gitea_insecure_tls_bypass_on_https"
    handler = HeldStartupHandler(name, failure=failure)
    logger = logging.getLogger(f"tests.api.startup.{tmp_path.name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    monkeypatch.setattr(api_startup_service, "LOGGER", logger)
    initialized, initialize = [], OrchestrationEngine.initialize

    async def observe_initialize(engine):
        initialized.append({"handler_finished": handler.finished.is_set(), "root": str(engine.workspace_root)})
        await initialize(engine)

    monkeypatch.setattr(OrchestrationEngine, "initialize", observe_initialize)
    return SimpleNamespace(app=app, handler=handler, logger=logger, initialized=initialized,
                           subscriber_baseline=event_subscriber_count(), admitted=False)


async def enter_api(probe):
    async with probe.app.router.lifespan_context(probe.app):
        probe.admitted = True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(probe.app), base_url="http://test") as client:
            assert (await client.get("/health")).status_code == 200


async def settle_api(task, probe):
    probe.handler.unblock.set()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    probe.logger.removeHandler(probe.handler)
    probe.handler.close()


def assert_closed(probe):
    owner = probe.app.state.api_runtime_context
    assert owner.closed and owner.active_request_count == owner.active_background_task_count == 0
    assert event_subscriber_count() == probe.subscriber_baseline
