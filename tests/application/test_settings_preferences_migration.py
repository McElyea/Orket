from __future__ import annotations

import importlib
import json
from pathlib import Path

import orket.settings as settings_module
import orket.runtime_paths as runtime_paths_module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_migrate_legacy_model_preferences_moves_keys_and_strips_user_settings(monkeypatch, tmp_path: Path):
    """Layer: contract. Verifies legacy model preferences migrate once, preserve settings, and mark completion."""
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
    assert preferences["_meta"]["migration_markers"]["legacy_model_preferences_v1"] is True

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "preferred_coder" not in saved_settings
    assert "preferred_operations_lead" not in saved_settings
    assert saved_settings["setup_complete"] is True


def test_load_user_preferences_returns_existing_models_without_legacy(monkeypatch, tmp_path: Path):
    """Layer: contract. Verifies preferences keep existing models and record migration completion without legacy rewrites."""
    settings_path = tmp_path / "user_settings.json"
    preferences_path = tmp_path / "preferences.json"
    _write_json(settings_path, {"setup_complete": True})
    _write_json(preferences_path, {"models": {"architect": "deepseek-r1:32b"}})

    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "PREFERENCES_FILE", preferences_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    preferences = settings_module.load_user_preferences()

    assert preferences["models"] == {"architect": "deepseek-r1:32b"}
    assert preferences["_meta"]["migration_markers"]["legacy_model_preferences_v1"] is True


def test_load_user_preferences_skips_second_migration_save_once_marker_exists(monkeypatch, tmp_path: Path):
    """Layer: contract. Verifies the persistent migration marker prevents repeat cold-start preference rewrites."""
    settings_path = tmp_path / "user_settings.json"
    preferences_path = tmp_path / "preferences.json"
    _write_json(settings_path, {"setup_complete": True})

    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "PREFERENCES_FILE", preferences_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    first = settings_module.load_user_preferences()
    assert first["_meta"]["migration_markers"]["legacy_model_preferences_v1"] is True

    save_calls: list[dict] = []
    real_save = settings_module.save_user_preferences

    def _capture_save(preferences: dict):
        save_calls.append(dict(preferences))
        return real_save(preferences)

    monkeypatch.setattr(settings_module, "save_user_preferences", _capture_save)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    second = settings_module.load_user_preferences()

    assert second["_meta"]["migration_markers"]["legacy_model_preferences_v1"] is True
    assert save_calls == []


def test_settings_import_has_no_config_directory_side_effect(monkeypatch, tmp_path: Path):
    """Layer: contract. Verifies importing settings/runtime paths does not create config directories before first access."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / ".orket" / "durable"))

    importlib.reload(runtime_paths_module)
    importlib.reload(settings_module)

    assert not (tmp_path / ".orket" / "durable" / "config").exists()
