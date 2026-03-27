import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, Optional

import aiofiles

from orket.runtime_paths import resolve_user_settings_path, resolve_user_preferences_path

ENV_FILE = Path(".env")
_SETTINGS_FILE: Path | None = None
_PREFERENCES_FILE: Path | None = None
_SETTINGS_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_META_KEY = "_meta"
_PREFERENCES_MIGRATION_MARKERS_KEY = "migration_markers"
_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY = "legacy_model_preferences_v1"
_ENV_LOADED = False


def set_settings_file(path: Path):
    global _SETTINGS_FILE, _SETTINGS_CACHE
    _SETTINGS_FILE = resolve_user_settings_path(path)
    _SETTINGS_CACHE = None


def set_preferences_file(path: Path):
    global _PREFERENCES_FILE, _PREFERENCES_CACHE
    _PREFERENCES_FILE = resolve_user_preferences_path(path)
    _PREFERENCES_CACHE = None


def _is_running_in_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _run_async_settings_call(awaitable: Any, *, operation: str) -> Any:
    if _is_running_in_event_loop():
        # Sync callers may still exist on async request paths; run file I/O on a
        # dedicated thread-backed event loop instead of doing sync I/O inline.
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, awaitable).result()
    return asyncio.run(awaitable)


async def _read_text_async(path: Path) -> str | None:
    if not await asyncio.to_thread(path.exists):
        return None
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return await handle.read()
    except OSError:
        return None


async def _read_json_async(path: Path) -> Dict[str, Any]:
    content = await _read_text_async(path)
    if content is None:
        return {}
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


async def _write_json_async(path: Path, payload: Dict[str, Any]) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=4)
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(rendered)


def _read_json_sync(path: Path, *, operation: str) -> Dict[str, Any]:
    return _run_async_settings_call(_read_json_async(path), operation=operation)


def _write_json_sync(path: Path, payload: Dict[str, Any], *, operation: str) -> None:
    _run_async_settings_call(_write_json_async(path, payload), operation=operation)


def load_env() -> None:
    """Simple .env loader to avoid extra dependencies."""
    global _ENV_LOADED
    # Keep tests hermetic: avoid re-injecting host .env values after monkeypatch.delenv.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if _ENV_LOADED:
        return
    if _is_running_in_event_loop():
        raise AssertionError("load_env must run before the event loop starts.")
    content = _run_async_settings_call(_read_text_async(ENV_FILE), operation="load_env")
    if content is not None:
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())
    _ENV_LOADED = True


def _get_settings_file() -> Path:
    global _SETTINGS_FILE
    if _SETTINGS_FILE is None:
        _SETTINGS_FILE = resolve_user_settings_path(create_parent=False, migrate_legacy=False)
    return _SETTINGS_FILE


def _get_preferences_file() -> Path:
    global _PREFERENCES_FILE
    if _PREFERENCES_FILE is None:
        _PREFERENCES_FILE = resolve_user_preferences_path(create_parent=False)
    return _PREFERENCES_FILE


def _default_settings_file() -> Path:
    return resolve_user_settings_path(create_parent=False, migrate_legacy=False)


def _default_preferences_file() -> Path:
    return resolve_user_preferences_path(create_parent=False)


def _settings_file_for_read() -> Path:
    settings_file = _get_settings_file()
    if settings_file == _default_settings_file():
        return resolve_user_settings_path(create_parent=False, migrate_legacy=True)
    return settings_file


def _settings_file_for_write() -> Path:
    settings_file = _get_settings_file()
    if settings_file == _default_settings_file():
        return resolve_user_settings_path(create_parent=True, migrate_legacy=True)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    return settings_file


def _preferences_file_for_read() -> Path:
    preferences_file = _get_preferences_file()
    if preferences_file == _default_preferences_file():
        return resolve_user_preferences_path(create_parent=False)
    return preferences_file


def _preferences_file_for_write() -> Path:
    preferences_file = _get_preferences_file()
    if preferences_file == _default_preferences_file():
        return resolve_user_preferences_path(create_parent=True)
    preferences_file.parent.mkdir(parents=True, exist_ok=True)
    return preferences_file


def _migration_markers(preferences: Dict[str, Any]) -> Dict[str, bool]:
    meta = preferences.get(_PREFERENCES_META_KEY)
    if not isinstance(meta, dict):
        meta = {}
        preferences[_PREFERENCES_META_KEY] = meta
    markers = meta.get(_PREFERENCES_MIGRATION_MARKERS_KEY)
    if not isinstance(markers, dict):
        markers = {}
        meta[_PREFERENCES_MIGRATION_MARKERS_KEY] = markers
    return markers


def _legacy_model_preferences_migration_done(preferences: Dict[str, Any]) -> bool:
    markers = _migration_markers(preferences)
    return bool(markers.get(_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY))


def _mark_legacy_model_preferences_migrated(preferences: Dict[str, Any]) -> Dict[str, Any]:
    markers = _migration_markers(preferences)
    markers[_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY] = True
    return preferences


def load_user_settings() -> Dict[str, Any]:
    """Loads settings from the project root with caching."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    search_paths = [_settings_file_for_read()]
    legacy = Path("user_settings.json")
    if legacy != _get_settings_file():
        search_paths.append(legacy)

    for settings_path in search_paths:
        if settings_path.exists():
            _SETTINGS_CACHE = _read_json_sync(settings_path, operation="load_user_settings")
            return _SETTINGS_CACHE
    return {}


async def load_user_settings_async() -> Dict[str, Any]:
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    search_paths = [_settings_file_for_read()]
    legacy = Path("user_settings.json")
    if legacy != _get_settings_file():
        search_paths.append(legacy)

    for settings_path in search_paths:
        if await asyncio.to_thread(settings_path.exists):
            _SETTINGS_CACHE = await _read_json_async(settings_path)
            return _SETTINGS_CACHE
    return {}


def save_user_settings(settings: Dict[str, Any]) -> None:
    """Saves settings to the project root and updates cache."""
    global _SETTINGS_CACHE
    settings_path = _settings_file_for_write()
    _write_json_sync(settings_path, settings, operation="save_user_settings")
    _SETTINGS_CACHE = settings


def _extract_legacy_model_preferences(settings: Dict[str, Any]) -> Dict[str, str]:
    migrated: Dict[str, str] = {}
    for key, value in settings.items():
        if not key.startswith("preferred_"):
            continue
        role = key[len("preferred_") :].strip()
        model = str(value or "").strip()
        if not role or not model:
            continue
        migrated[role] = model
    return migrated


async def save_user_settings_async(settings: Dict[str, Any]) -> None:
    global _SETTINGS_CACHE
    settings_path = _settings_file_for_write()
    await _write_json_async(settings_path, settings)
    _SETTINGS_CACHE = settings


def save_user_preferences(preferences: Dict[str, Any]) -> None:
    """Saves preference settings and updates cache."""
    global _PREFERENCES_CACHE
    preferences_path = _preferences_file_for_write()
    _write_json_sync(preferences_path, preferences, operation="save_user_preferences")
    _PREFERENCES_CACHE = preferences


async def save_user_preferences_async(preferences: Dict[str, Any]) -> None:
    global _PREFERENCES_CACHE
    preferences_path = _preferences_file_for_write()
    await _write_json_async(preferences_path, preferences)
    _PREFERENCES_CACHE = preferences


def migrate_legacy_model_preferences() -> Dict[str, Any]:
    """
    Hard migration: move legacy preferred_* model keys out of user_settings.json
    into preferences.json under {"models": {"<role>": "<model>"}}.
    """
    global _SETTINGS_CACHE, _PREFERENCES_CACHE

    settings = load_user_settings().copy()
    preferences = _read_json_sync(_preferences_file_for_read(), operation="load_user_preferences")
    if _legacy_model_preferences_migration_done(preferences):
        return preferences
    legacy_models = _extract_legacy_model_preferences(settings)
    if not legacy_models:
        preferences = _mark_legacy_model_preferences_migrated(preferences)
        save_user_preferences(preferences)
        return preferences

    existing_models = preferences.get("models")
    models = dict(existing_models) if isinstance(existing_models, dict) else {}
    for role, model in legacy_models.items():
        models[str(role).strip()] = model

    preferences["models"] = models
    preferences = _mark_legacy_model_preferences_migrated(preferences)
    save_user_preferences(preferences)

    for role in legacy_models.keys():
        settings.pop(f"preferred_{role}", None)
    save_user_settings(settings)

    _SETTINGS_CACHE = settings
    _PREFERENCES_CACHE = preferences
    return preferences


def load_user_preferences() -> Dict[str, Any]:
    global _PREFERENCES_CACHE
    if _PREFERENCES_CACHE is not None:
        return _PREFERENCES_CACHE

    _PREFERENCES_CACHE = migrate_legacy_model_preferences()
    return _PREFERENCES_CACHE


async def load_user_preferences_async() -> Dict[str, Any]:
    global _PREFERENCES_CACHE
    if _PREFERENCES_CACHE is not None:
        return _PREFERENCES_CACHE

    _PREFERENCES_CACHE = await asyncio.to_thread(migrate_legacy_model_preferences)
    return _PREFERENCES_CACHE


def get_setting(key: str, default: Any = None) -> Any:
    # Check environment first (UPPERCASE)
    env_val = os.environ.get(key.upper())
    if env_val is not None:
        return env_val

    settings = load_user_settings()
    return settings.get(key, default)


def update_setting(key: str, value: Any):
    settings = load_user_settings().copy()
    settings[key] = value
    save_user_settings(settings)
