from __future__ import annotations

import json
from pathlib import Path

import orket.settings as settings_module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_migrate_legacy_model_preferences_moves_keys_and_strips_user_settings(monkeypatch, tmp_path: Path):
    settings_path = tmp_path / "user_settings.json"
    preferences_path = tmp_path / "preferences.json"
    _write_json(
        settings_path,
        {
            "setup_complete": True,
            "hardware_profile": "auto-detected",
            "preferred_coder": "qwen2.5-coder:14b",
            "preferred_operations_lead": "llama3.3:70b",
        },
    )

    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "PREFERENCES_FILE", preferences_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    preferences = settings_module.load_user_preferences()

    assert preferences["models"]["coder"] == "qwen2.5-coder:14b"
    assert preferences["models"]["operations_lead"] == "llama3.3:70b"

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "preferred_coder" not in saved_settings
    assert "preferred_operations_lead" not in saved_settings
    assert saved_settings["setup_complete"] is True


def test_load_user_preferences_returns_existing_models_without_legacy(monkeypatch, tmp_path: Path):
    settings_path = tmp_path / "user_settings.json"
    preferences_path = tmp_path / "preferences.json"
    _write_json(settings_path, {"setup_complete": True})
    _write_json(preferences_path, {"models": {"architect": "deepseek-r1:32b"}})

    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "PREFERENCES_FILE", preferences_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    preferences = settings_module.load_user_preferences()

    assert preferences == {"models": {"architect": "deepseek-r1:32b"}}
