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
