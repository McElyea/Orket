"""Integration: selected construction inputs survive real driver and API owners."""
# Layer: integration
from __future__ import annotations

import os
from pathlib import Path

import pytest

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.driver import OrketDriver
from orket.interfaces.api import create_api_app
from tests.integration.test_model_selection_consumers import _environment

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_real_driver_uses_explicit_inputs_without_recapture_and_closes(
    tmp_path, monkeypatch,
) -> None:
    environment = _environment("http://127.0.0.1:1/v1")
    environment.pop("ORKET_OPERATOR_MODEL", None)
    environment.pop("ORKET_MODEL_OPERATIONS_LEAD", None)
    inputs = RuntimeConstructionInputs(
        tmp_path.resolve(), environment, "{}", '{"models":{"operations_lead":"selected-input-model"}}')

    async def refuse_capture(cls, **_options):
        pytest.fail("explicit driver inputs cannot trigger ambient capture")

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(refuse_capture))
    driver = None
    try:
        driver = await OrketDriver.create(
            project_root=Path("project"), construction_inputs=inputs, strict_config=False)
        assert driver.project_root == tmp_path / "project"
        environment_matches = dict(driver._environment) == dict(inputs.environment)
        assert environment_matches
        assert driver.provider.model == "selected-input-model"
        assert driver.provider.client.is_closed is False
    finally:
        if driver is not None:
            await driver.close()
    assert driver is not None and driver.provider.client.is_closed


# Layer: integration
async def test_two_api_apps_forward_their_own_inputs_and_close_every_owner(
    tmp_path, monkeypatch,
) -> None:
    from orket import driver as driver_module

    roots = [tmp_path / "one", tmp_path / "two"]
    for root in roots:
        root.mkdir()
    apps = [create_api_app(project_root=root, environment={
        **os.environ,
        "ORKET_API_KEY": f"key-{index}",
        "ORKET_DISABLE_SANDBOX": "1",
    }) for index, root in enumerate(roots, start=1)]
    expected = [app.state.api_preparation.inputs for app in apps]
    calls = []
    drivers = []

    class DriverProbe:
        def __init__(self, inputs) -> None:
            self.inputs = inputs
            self.closed = False

        async def close(self) -> None:
            self.closed = True

    async def create(cls, *args, **options):
        assert args == ()
        assert set(options) == {"project_root", "construction_inputs"}
        driver = DriverProbe(options["construction_inputs"])
        calls.append(options)
        drivers.append(driver)
        return driver

    monkeypatch.setattr(driver_module.OrketDriver, "create", classmethod(create))
    for app, selected in zip(apps, expected, strict=True):
        async with app.router.lifespan_context(app):
            container = app.state.api_runtime_context
            host = container.api_runtime_host
            assert host.construction_inputs is selected
            driver = await host.create_chat_driver()
            try:
                assert driver.inputs is selected
            finally:
                await host.close_chat_driver(driver)
            assert driver.closed
        assert app.state.api_runtime_context.closed
    assert expected[0] is not expected[1]
    input_identities_match = len(calls) == len(expected) and all(
        call["construction_inputs"] is selected
        for call, selected in zip(calls, expected, strict=True)
    )
    assert input_identities_match
    assert all(driver.closed for driver in drivers)
