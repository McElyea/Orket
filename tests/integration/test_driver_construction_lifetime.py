"""Driver factory captures real inputs and refuses unsafe synchronous embedding."""
import asyncio
import threading

import pytest

from orket.driver import OrketDriver
from orket.settings import load_user_preferences, set_runtime_settings_context
from tests.integration.test_model_selection_consumers import _environment

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_driver_sync_constructor_refuses_event_loop_before_filesystem_or_provider(tmp_path):
    project = tmp_path / "uncreated"
    with pytest.raises(RuntimeError, match="E_DRIVER_CONSTRUCTION_REQUIRES_WORKER"):
        OrketDriver(project_root=project, environment={})
    assert not await asyncio.to_thread(project.exists)


async def test_driver_factory_keeps_root_environment_and_settings(test_root, tmp_path, monkeypatch):
    project = test_root / "selected"
    await asyncio.to_thread(project.mkdir)
    monkeypatch.chdir(test_root)
    environment = _environment("http://127.0.0.1:1/v1")
    original = OrketDriver.__init__
    entered, release = threading.Event(), threading.Event()
    observed = {}

    def construct(self, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        observed["preferences"] = load_user_preferences()
        original(self, *args, **kwargs)

    monkeypatch.setattr(OrketDriver, "__init__", construct)
    set_runtime_settings_context(user_settings={}, user_preferences={"models": {"coder": "before"}})
    task = asyncio.create_task(OrketDriver.create(project_root="selected", environment=environment))
    owner = None
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        environment["ORKET_MODEL_CLIENT_NODE"] = "retired-later"
        monkeypatch.chdir(tmp_path.parent)
        monkeypatch.setenv("ORKET_MODEL_CLIENT_NODE", "retired-ambient")
        set_runtime_settings_context(user_settings={}, user_preferences={"models": {"coder": "after"}})
        release.set()
        owner = await asyncio.wait_for(task, 5)
        assert owner.project_root == project
        assert "ORKET_MODEL_CLIENT_NODE" not in owner._environment
        assert observed["preferences"]["models"]["coder"] == "before"
        assert owner.provider.client.is_closed is False
    finally:
        release.set()
        settled = await asyncio.gather(task, return_exceptions=True)
        if isinstance(settled[0], OrketDriver):
            await settled[0].close()
    assert owner.provider.client.is_closed


async def test_driver_factory_owns_explicit_provider_cleanup(test_root):
    from orket.adapters.storage.async_file_tools import AsyncFileTools
    from orket.application.services.local_model_factory import create_local_model_provider
    from orket.application.services.reforger_service import ReforgerService

    environment = _environment("http://127.0.0.1:1/v1")
    provider = await asyncio.to_thread(create_local_model_provider, model="fixture", environment=environment)
    fs = await asyncio.to_thread(AsyncFileTools, test_root)
    reforger = await asyncio.to_thread(ReforgerService, test_root / "workspace", [test_root])
    try:
        driver = await OrketDriver.create(project_root=test_root, environment={}, provider=provider,
                                          fs=fs, reforger_tools=reforger, strict_config=False)
        assert driver.provider is provider and driver.fs is fs and driver.reforger_tools is reforger
        await driver.close()
        await driver.close()
        assert provider.client.is_closed
    finally:
        await provider.close()
