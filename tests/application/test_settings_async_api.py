from __future__ import annotations

import json
from pathlib import Path

import pytest

import orket.settings as settings_module
from orket.exceptions import SettingsBridgeError


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_load_user_settings_async_reads_settings_inside_event_loop(monkeypatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies the async settings API reads user settings without a sync bridge."""
    settings_path = tmp_path / "user_settings.json"
    _write_json(settings_path, {"state_backend_mode": "sqlite"})

    monkeypatch.setattr(settings_module, "_SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)

    settings = await settings_module.load_user_settings_async()

    assert settings["state_backend_mode"] == "sqlite"


@pytest.mark.asyncio
async def test_load_user_settings_sync_fails_closed_inside_event_loop_without_runtime_context(
    monkeypatch, tmp_path: Path
) -> None:
    """Layer: unit. Verifies sync settings reads fail closed on async paths unless runtime context is bound."""
    settings_path = tmp_path / "user_settings.json"
    _write_json(settings_path, {"state_backend_mode": "sqlite"})

    monkeypatch.setattr(settings_module, "_SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)

    with pytest.raises(SettingsBridgeError, match="set_runtime_settings_context"):
        settings_module.load_user_settings()


@pytest.mark.asyncio
async def test_runtime_settings_context_allows_sync_reads_inside_event_loop() -> None:
    """Layer: unit. Verifies async runtime code can bind a settings snapshot for sync helper consumers."""
    settings_module.set_runtime_settings_context(
        user_settings={"state_backend_mode": "sqlite"},
        user_preferences={"models": {"coder": "qwen2.5-coder:14b"}},
    )

    assert settings_module.load_user_settings()["state_backend_mode"] == "sqlite"
    assert settings_module.load_user_preferences()["models"]["coder"] == "qwen2.5-coder:14b"

    settings_module.clear_runtime_settings_context()


@pytest.mark.asyncio
async def test_load_user_preferences_async_migrates_legacy_preferences(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies async preference loading performs the legacy migration without sync wrappers."""
    settings_path = tmp_path / "user_settings.json"
    preferences_path = tmp_path / "preferences.json"
    _write_json(settings_path, {"preferred_coder": "qwen2.5-coder:14b", "setup_complete": True})

    monkeypatch.setattr(settings_module, "_SETTINGS_FILE", settings_path)
    monkeypatch.setattr(settings_module, "_PREFERENCES_FILE", preferences_path)
    monkeypatch.setattr(settings_module, "_SETTINGS_CACHE", None)
    monkeypatch.setattr(settings_module, "_PREFERENCES_CACHE", None)

    preferences = await settings_module.load_user_preferences_async()

    assert preferences["models"]["coder"] == "qwen2.5-coder:14b"
    assert preferences["_meta"]["migration_markers"]["legacy_model_preferences_v1"] is True

    saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "preferred_coder" not in saved_settings
