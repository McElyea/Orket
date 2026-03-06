from __future__ import annotations

from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver


class _AlwaysMissingLoader:
    def __init__(self, *_args, **_kwargs):
        return None

    def load_asset(self, asset_kind, asset_name, _schema):
        raise FileNotFoundError(f"missing {asset_kind}/{asset_name}")


def test_load_engine_configs_marks_degraded_and_emits_mode_event(monkeypatch):
    """Layer: contract. Verifies explicit degradation markers and telemetry for config load failures."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.ConfigLoader", _AlwaysMissingLoader)
    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.provider = SimpleNamespace(model="qwen2.5-coder")
    driver.strict_config_mode = False

    driver._load_engine_configs()

    assert driver.prompting_mode == "fallback"
    assert driver.config_degraded is True
    assert driver.config_dependency_classification["skill.operations_lead"] == "degradable"
    assert driver.config_dependency_classification["dialect.qwen"] == "degradable"
    assert any(name == "driver_config_dependency_failed" for name, _ in events)
    assert any(name == "driver_prompting_mode" and payload["mode"] == "fallback" for name, payload in events)


def test_load_engine_configs_strict_mode_fails_closed(monkeypatch):
    """Layer: unit. Verifies strict mode blocks fallback prompting on missing config assets."""
    monkeypatch.setattr("orket.driver.ConfigLoader", _AlwaysMissingLoader)
    monkeypatch.setattr("orket.driver.log_event", lambda *_args, **_kwargs: None)
    driver = OrketDriver.__new__(OrketDriver)
    driver.provider = SimpleNamespace(model="llama3.1")
    driver.strict_config_mode = True

    with pytest.raises(RuntimeError, match="strict config mode"):
        driver._load_engine_configs()
