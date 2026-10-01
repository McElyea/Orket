from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver
from tests.helpers.logging_fixture_owner import prepared_fixture_owner
from tests.helpers.model_selection import prepared_model_selection


class _FakeProvider:
    def __init__(self, model, temperature=0.1, *, environment=None, cwd=None):
        self.model, self.cwd, self.environment = model, cwd, dict(environment)
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.contract
def test_parse_model_plan_compatibility_mode_accepts_wrapped_json(monkeypatch):
    """Layer: contract. Verifies compatibility mode supports envelope extraction and emits mode telemetry."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver_support_conversation.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.json_parse_mode = "compatibility"

    plan = driver._parse_model_plan('prefix {"action":"converse","reasoning":"ok"} suffix')

    assert plan["action"] == "converse"
    assert ("driver_json_parse_mode_compatibility", {"mode": "compatibility"}) in events


@pytest.mark.contract
def test_driver_defaults_to_strict_json_for_governed_prompting(monkeypatch, tmp_path):
    """Layer: contract. Verifies governed driver construction defaults to strict JSON parsing."""

    def _fake_load_engine_configs(self) -> None:
        self.skill = object()
        self.dialect = object()
        self.prompting_mode = "governed"
        self.config_degraded = False
        self.config_dependency_classification = {}
        self.config_load_failures = []

    monkeypatch.setattr("orket.driver.create_local_model_provider", _FakeProvider)
    monkeypatch.setattr("orket.driver.prepare_bootstrap_model_selection", lambda **kwargs: prepared_model_selection())
    monkeypatch.setattr(OrketDriver, "_load_engine_configs", _fake_load_engine_configs)

    driver = OrketDriver(model="qwen3.5-coder", project_root=tmp_path, environment={}, invocation_root=tmp_path)
    try:
        assert driver.json_parse_mode == "strict"
        assert driver.provider.cwd == tmp_path and driver.provider.environment == {}
    finally:
        asyncio.run(driver.close())
    assert driver.provider.closed


@pytest.mark.unit
def test_driver_explicit_compatibility_override_survives_governed_prompting(monkeypatch, tmp_path):
    """Layer: unit. Verifies explicit compatibility mode stays opt-in even on governed paths."""

    def _fake_load_engine_configs(self) -> None:
        self.skill = object()
        self.dialect = object()
        self.prompting_mode = "governed"
        self.config_degraded = False
        self.config_dependency_classification = {}
        self.config_load_failures = []

    monkeypatch.setattr("orket.driver.create_local_model_provider", _FakeProvider)
    monkeypatch.setattr("orket.driver.prepare_bootstrap_model_selection", lambda **kwargs: prepared_model_selection())
    monkeypatch.setattr(OrketDriver, "_load_engine_configs", _fake_load_engine_configs)

    driver = OrketDriver(model="qwen3.5-coder", json_parse_mode="compatibility", project_root=tmp_path,
                         environment={}, invocation_root=tmp_path)
    try:
        assert driver.json_parse_mode == "compatibility"
        assert driver.provider.cwd == tmp_path and driver.provider.environment == {}
    finally:
        asyncio.run(driver.close())
    assert driver.provider.closed


@pytest.mark.unit
def test_parse_model_plan_strict_mode_rejects_wrapped_json(monkeypatch):
    """Layer: unit. Verifies strict mode rejects non-envelope output and emits strict mode telemetry."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver_support_conversation.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.json_parse_mode = "strict"

    with pytest.raises(ValueError, match="Strict JSON mode requires pure JSON envelope output."):
        driver._parse_model_plan('prefix {"action":"converse","reasoning":"ok"} suffix')

    assert ("driver_json_parse_mode_strict", {"mode": "strict"}) in events


@pytest.mark.asyncio
@pytest.mark.contract
async def test_process_request_strict_mode_rejects_non_json_envelope_output(tmp_path):
    """Verifies strict mode through the driver with controlled model output."""
    driver = await prepared_fixture_owner(OrketDriver, tmp_path)
    driver.project_root, driver.model_root = tmp_path, tmp_path / "model"
    driver._environment = {}
    await asyncio.to_thread(driver.model_root.mkdir)
    driver.skill = None
    driver.dialect = None
    driver.json_parse_mode = "strict"

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(content='note: {"action":"converse","reasoning":"ok"}')

    driver.provider = _Provider()

    response = await driver.process_request("settings")

    assert "Driver failed to parse JSON" in response
    assert "Strict JSON mode requires pure JSON envelope output." in response


@pytest.mark.asyncio
@pytest.mark.contract
async def test_process_request_compatibility_mode_surfaces_degraded_parse(monkeypatch, tmp_path):
    """Verifies controlled non-JSON output produces a visible compatibility warning."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = await prepared_fixture_owner(OrketDriver, tmp_path)
    driver.project_root, driver.model_root = tmp_path, tmp_path / "model"
    driver._environment = {}
    await asyncio.to_thread(driver.model_root.mkdir)
    driver.skill = None
    driver.dialect = None
    driver.json_parse_mode = "compatibility"

    class _Provider:
        async def complete(self, _messages):
            return SimpleNamespace(content='note: {"action":"converse","response":"ok","reasoning":"ok"}')

    driver.provider = _Provider()

    response = await driver.process_request("settings")

    assert response.startswith("[DEGRADED] Compatibility mode extracted JSON")
    assert response.endswith("ok")
    assert ("driver_json_parse_compatibility_fallback_used", {"mode": "compatibility"}) in events
