from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver


def test_parse_model_plan_compatibility_mode_accepts_wrapped_json(monkeypatch):
    """Layer: contract. Verifies compatibility mode supports envelope extraction and emits mode telemetry."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.json_parse_mode = "compatibility"

    plan = driver._parse_model_plan('prefix {"action":"converse","reasoning":"ok"} suffix')

    assert plan["action"] == "converse"
    assert ("driver_json_parse_mode_compatibility", {"mode": "compatibility"}) in events


def test_driver_defaults_to_strict_json_for_governed_prompting(monkeypatch):
    """Layer: contract. Verifies governed driver construction defaults to strict JSON parsing."""

    class _FakeProvider:
        def __init__(self, model, temperature=0.1):  # type: ignore[no-untyped-def]
            self.model = model

    class _FakeSelector:
        def __init__(self, organization=None):  # type: ignore[no-untyped-def]
            _ = organization

        def select(self, role, override=None):  # type: ignore[no-untyped-def]
            _ = role
            return override or "qwen3.5-coder"

    def _fake_load_engine_configs(self) -> None:
        self.skill = object()
        self.dialect = object()
        self.prompting_mode = "governed"
        self.config_degraded = False
        self.config_dependency_classification = {}
        self.config_load_failures = []

    monkeypatch.setattr("orket.driver.LocalModelProvider", _FakeProvider)
    monkeypatch.setattr("orket.orchestration.models.ModelSelector", _FakeSelector)
    monkeypatch.setattr(OrketDriver, "_load_engine_configs", _fake_load_engine_configs)

    driver = OrketDriver(model="qwen3.5-coder")

    assert driver.json_parse_mode == "strict"


def test_driver_explicit_compatibility_override_survives_governed_prompting(monkeypatch):
    """Layer: unit. Verifies explicit compatibility mode stays opt-in even on governed paths."""

    class _FakeProvider:
        def __init__(self, model, temperature=0.1):  # type: ignore[no-untyped-def]
            self.model = model

    class _FakeSelector:
        def __init__(self, organization=None):  # type: ignore[no-untyped-def]
            _ = organization

        def select(self, role, override=None):  # type: ignore[no-untyped-def]
            _ = role
            return override or "qwen3.5-coder"

    def _fake_load_engine_configs(self) -> None:
        self.skill = object()
        self.dialect = object()
        self.prompting_mode = "governed"
        self.config_degraded = False
        self.config_dependency_classification = {}
        self.config_load_failures = []

    monkeypatch.setattr("orket.driver.LocalModelProvider", _FakeProvider)
    monkeypatch.setattr("orket.orchestration.models.ModelSelector", _FakeSelector)
    monkeypatch.setattr(OrketDriver, "_load_engine_configs", _fake_load_engine_configs)

    driver = OrketDriver(model="qwen3.5-coder", json_parse_mode="compatibility")

    assert driver.json_parse_mode == "compatibility"


def test_parse_model_plan_strict_mode_rejects_wrapped_json(monkeypatch):
    """Layer: unit. Verifies strict mode rejects non-envelope output and emits strict mode telemetry."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.json_parse_mode = "strict"

    with pytest.raises(ValueError, match="Strict JSON mode requires pure JSON envelope output."):
        driver._parse_model_plan('prefix {"action":"converse","reasoning":"ok"} suffix')

    assert ("driver_json_parse_mode_strict", {"mode": "strict"}) in events


@pytest.mark.asyncio
async def test_process_request_strict_mode_rejects_non_json_envelope_output():
    """Layer: integration. Verifies strict mode behavior on model output variants through runtime path."""
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
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
async def test_process_request_compatibility_mode_surfaces_degraded_parse(monkeypatch):
    """Layer: integration. Verifies compatibility extraction is surfaced as degraded operator-visible behavior."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.model_root = Path("model")
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
