"""Layer: contract. Runtime construction inputs distinguish omitted and captured preferences."""
from __future__ import annotations

import pytest

import orket.application.services.runtime_construction_inputs as inputs_module
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs

pytestmark = pytest.mark.contract


def test_selective_sync_capture_skips_preferences_and_fails_before_binding(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    published = []
    monkeypatch.setattr(inputs_module, "load_user_settings", lambda: {"selected": "settings"})

    def refuse_preferences():
        pytest.fail("Selective native capture cannot observe preferences")

    monkeypatch.setattr(inputs_module, "load_user_preferences", refuse_preferences)
    monkeypatch.setattr(inputs_module, "set_runtime_settings_context", lambda **values: published.append(values))
    captured = RuntimeConstructionInputs.capture(
        environment={"ORKET_LLM_PROVIDER": "captured"}, capture_preferences=False,
    )

    assert captured.invocation_root == tmp_path
    assert dict(captured.environment) == {"ORKET_LLM_PROVIDER": "captured"}
    assert captured.user_settings() == {"selected": "settings"}
    assert captured.user_preferences_json is None
    with pytest.raises(ValueError, match="^E_RUNTIME_PREFERENCES_NOT_CAPTURED$"):
        captured.user_preferences()
    with pytest.raises(ValueError, match="^E_RUNTIME_PREFERENCES_NOT_CAPTURED$"):
        captured.bind_settings()
    assert published == []


def test_full_sync_capture_remains_default_and_binds_one_complete_snapshot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    published = []
    monkeypatch.setattr(inputs_module, "load_user_settings", lambda: {"selected": "settings"})
    monkeypatch.setattr(inputs_module, "load_user_preferences", lambda: {"theme": "captured"})
    monkeypatch.setattr(inputs_module, "set_runtime_settings_context", lambda **values: published.append(values))

    captured = RuntimeConstructionInputs.capture(environment={"ORKET_LLM_PROVIDER": "captured"})
    captured.bind_settings()

    assert captured.user_settings() == {"selected": "settings"}
    assert captured.user_preferences() == {"theme": "captured"}
    assert published == [{
        "user_settings": {"selected": "settings"},
        "user_preferences": {"theme": "captured"},
        "environment": captured.environment,
    }]
