import asyncio
import contextvars
import json
import logging
import os
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

import aiofiles
from dotenv import dotenv_values

from orket.exceptions import SettingsBridgeError
from orket.runtime_paths import resolve_user_preferences_path, resolve_user_settings_path

ENV_FILE = Path(".env")
_SETTINGS_FILE: Path | None = None
_PREFERENCES_FILE: Path | None = None
_SETTINGS_CACHE: dict[str, Any] | None = None
_PREFERENCES_CACHE: dict[str, Any] | None = None
_PREFERENCES_META_KEY = "_meta"
_PREFERENCES_MIGRATION_MARKERS_KEY = "migration_markers"
_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY = "legacy_model_preferences_v1"
_ENV_LOADED = False
_ENV_LOADED_LOCK = threading.Lock()
_SETTINGS_CACHE_LOCK = threading.RLock()
ResultT = TypeVar("ResultT")
_RUNTIME_USER_SETTINGS: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "runtime_user_settings",
    default=None,
)
_RUNTIME_USER_PREFERENCES: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "runtime_user_preferences",
    default=None,
)


def set_settings_file(path: Path) -> None:
    global _SETTINGS_FILE
    _SETTINGS_FILE = resolve_user_settings_path(path)
    _set_cache("_SETTINGS_CACHE", None)


def set_preferences_file(path: Path) -> None:
    global _PREFERENCES_FILE
    _PREFERENCES_FILE = resolve_user_preferences_path(path)
    _set_cache("_PREFERENCES_CACHE", None)


def _is_running_in_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _run_settings_sync(awaitable: Coroutine[Any, Any, ResultT], *, operation: str) -> ResultT:
    """Run settings async helpers for sync callers.

    Settings injected via set_runtime_settings_context() are not visible to sync callers using this bridge.
    """
    if _RUNTIME_USER_SETTINGS.get() is not None or _RUNTIME_USER_PREFERENCES.get() is not None:
        logging.getLogger("orket.settings").warning(
            "runtime settings context is not visible to _run_settings_sync callers",
            extra={"operation": operation},
        )
    if _is_running_in_event_loop():
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise SettingsBridgeError(
            f"{operation} must run before the event loop starts or after set_runtime_settings_context()."
        )
    return asyncio.run(awaitable)


def _settings_cache_enabled() -> bool:
    return not bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _read_cache(name: str) -> dict[str, Any] | None:
    with _SETTINGS_CACHE_LOCK:
        cached = globals()[name]
        return dict(cached) if isinstance(cached, dict) else None


def _set_cache(name: str, payload: dict[str, Any] | None) -> None:
    with _SETTINGS_CACHE_LOCK:
        globals()[name] = dict(payload) if isinstance(payload, dict) else None


def set_runtime_settings_context(
    *,
    user_settings: dict[str, Any] | None = None,
    user_preferences: dict[str, Any] | None = None,
) -> None:
    if user_settings is not None:
        _RUNTIME_USER_SETTINGS.set(dict(user_settings))
    if user_preferences is not None:
        _RUNTIME_USER_PREFERENCES.set(dict(user_preferences))


def clear_runtime_settings_context() -> None:
    _RUNTIME_USER_SETTINGS.set(None)
    _RUNTIME_USER_PREFERENCES.set(None)


def clear_settings_cache() -> None:
    global _SETTINGS_FILE, _PREFERENCES_FILE, _ENV_LOADED
    _SETTINGS_FILE = None
    _PREFERENCES_FILE = None
    _set_cache("_SETTINGS_CACHE", None)
    _set_cache("_PREFERENCES_CACHE", None)
    clear_runtime_settings_context()
    with _ENV_LOADED_LOCK:
        _ENV_LOADED = False


async def _read_text_async(path: Path) -> str | None:
    if not await asyncio.to_thread(path.exists):
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as handle:
            return await handle.read()
    except OSError:
        return None


async def _read_json_async(path: Path) -> dict[str, Any]:
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


async def _write_json_async(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=4)
    async with aiofiles.open(path, "w", encoding="utf-8") as handle:
        await handle.write(rendered)


def load_env() -> None:
    """Load .env values before event loop startup."""
    global _ENV_LOADED
    # Keep tests hermetic: avoid re-injecting host .env values after monkeypatch.delenv.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    with _ENV_LOADED_LOCK:
        if _ENV_LOADED:
            return
        if _is_running_in_event_loop():
            raise SettingsBridgeError("load_env must run before the event loop starts.")
        for key, value in dotenv_values(ENV_FILE).items():
            if key and value is not None:
                os.environ.setdefault(str(key).strip(), str(value))
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
    return preferences_file


def _settings_search_paths() -> list[Path]:
    search_paths = [_settings_file_for_read()]
    legacy = Path("user_settings.json")
    if legacy != _get_settings_file():
        search_paths.append(legacy)
    return search_paths


def _migration_markers(preferences: dict[str, Any]) -> dict[str, bool]:
    meta = preferences.get(_PREFERENCES_META_KEY)
    if not isinstance(meta, dict):
        meta = {}
        preferences[_PREFERENCES_META_KEY] = meta
    markers = meta.get(_PREFERENCES_MIGRATION_MARKERS_KEY)
    if not isinstance(markers, dict):
        markers = {}
        meta[_PREFERENCES_MIGRATION_MARKERS_KEY] = markers
    return markers


def _legacy_model_preferences_migration_done(preferences: dict[str, Any]) -> bool:
    markers = _migration_markers(preferences)
    return bool(markers.get(_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY))


def _mark_legacy_model_preferences_migrated(preferences: dict[str, Any]) -> dict[str, Any]:
    markers = _migration_markers(preferences)
    markers[_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY] = True
    return preferences


async def load_user_settings_async() -> dict[str, Any]:
    cache_enabled = _settings_cache_enabled()
    cached = _read_cache("_SETTINGS_CACHE")
    if cache_enabled and cached is not None:
        return cached
    if os.environ.get("PYTEST_CURRENT_TEST") and _SETTINGS_FILE is None:
        return {}

    for settings_path in _settings_search_paths():
        if await asyncio.to_thread(settings_path.exists):
            settings = await _read_json_async(settings_path)
            if cache_enabled:
                _set_cache("_SETTINGS_CACHE", settings)
            return settings
    return {}


def load_user_settings() -> dict[str, Any]:
    """Loads settings from the project root for sync callers outside the event loop."""
    runtime_settings = _RUNTIME_USER_SETTINGS.get()
    if isinstance(runtime_settings, dict):
        return dict(runtime_settings)
    if os.environ.get("PYTEST_CURRENT_TEST") and _SETTINGS_FILE is None:
        return {}
    cached = _read_cache("_SETTINGS_CACHE")
    if cached is not None:
        return cached
    if _is_running_in_event_loop() and not any(path.exists() for path in _settings_search_paths()):
        return {}
    return _run_settings_sync(load_user_settings_async(), operation="load_user_settings")


def _extract_legacy_model_preferences(settings: dict[str, Any]) -> dict[str, str]:
    migrated: dict[str, str] = {}
    for key, value in settings.items():
        if not key.startswith("preferred_"):
            continue
        role = key[len("preferred_") :].strip()
        model = str(value or "").strip()
        if not role or not model:
            continue
        migrated[role] = model
    return migrated


async def save_user_settings_async(settings: dict[str, Any]) -> None:
    settings_path = _settings_file_for_write()
    await _write_json_async(settings_path, settings)
    _set_cache("_SETTINGS_CACHE", dict(settings) if _settings_cache_enabled() else None)


def save_user_settings(settings: dict[str, Any]) -> None:
    """Saves settings for sync callers outside the event loop."""
    _run_settings_sync(save_user_settings_async(settings), operation="save_user_settings")


async def save_user_preferences_async(preferences: dict[str, Any]) -> None:
    preferences_path = _preferences_file_for_write()
    await _write_json_async(preferences_path, preferences)
    _set_cache("_PREFERENCES_CACHE", dict(preferences) if _settings_cache_enabled() else None)


def save_user_preferences(preferences: dict[str, Any]) -> None:
    """Saves preferences for sync callers outside the event loop."""
    _run_settings_sync(save_user_preferences_async(preferences), operation="save_user_preferences")


async def migrate_legacy_model_preferences_async() -> dict[str, Any]:
    """
    Hard migration: move legacy preferred_* model keys out of user_settings.json
    into preferences.json under {"models": {"<role>": "<model>"}}.
    """
    settings = (await load_user_settings_async()).copy()
    preferences = await _read_json_async(_preferences_file_for_read())
    if _legacy_model_preferences_migration_done(preferences):
        return preferences
    legacy_models = _extract_legacy_model_preferences(settings)
    if not legacy_models:
        preferences = _mark_legacy_model_preferences_migrated(preferences)
        await save_user_preferences_async(preferences)
        return preferences

    existing_models = preferences.get("models")
    models = dict(existing_models) if isinstance(existing_models, dict) else {}
    for role, model in legacy_models.items():
        models[str(role).strip()] = model

    preferences["models"] = models
    preferences = _mark_legacy_model_preferences_migrated(preferences)
    await save_user_preferences_async(preferences)

    for role in legacy_models:
        settings.pop(f"preferred_{role}", None)
    await save_user_settings_async(settings)
    return preferences


def migrate_legacy_model_preferences() -> dict[str, Any]:
    return _run_settings_sync(
        migrate_legacy_model_preferences_async(),
        operation="migrate_legacy_model_preferences",
    )


def load_user_preferences() -> dict[str, Any]:
    runtime_preferences = _RUNTIME_USER_PREFERENCES.get()
    if isinstance(runtime_preferences, dict):
        return dict(runtime_preferences)
    if os.environ.get("PYTEST_CURRENT_TEST") and _SETTINGS_FILE is None and _PREFERENCES_FILE is None:
        return {}
    cached = _read_cache("_PREFERENCES_CACHE")
    if cached is not None:
        return cached
    if _is_running_in_event_loop():
        preferences_path = _preferences_file_for_read()
        if not preferences_path.exists() and not any(path.exists() for path in _settings_search_paths()):
            return {}
    return _run_settings_sync(load_user_preferences_async(), operation="load_user_preferences")


async def load_user_preferences_async() -> dict[str, Any]:
    cache_enabled = _settings_cache_enabled()
    cached = _read_cache("_PREFERENCES_CACHE")
    if cache_enabled and cached is not None:
        return cached
    if os.environ.get("PYTEST_CURRENT_TEST") and _SETTINGS_FILE is None and _PREFERENCES_FILE is None:
        return {}

    preferences = await migrate_legacy_model_preferences_async()
    if cache_enabled:
        _set_cache("_PREFERENCES_CACHE", preferences)
    return preferences


def get_setting(key: str, default: Any = None) -> Any:
    # Check environment first (UPPERCASE)
    env_val = os.environ.get(key.upper())
    if env_val is not None:
        return env_val

    settings = load_user_settings()
    return settings.get(key, default)


def update_setting(key: str, value: Any) -> None:
    settings = load_user_settings().copy()
    settings[key] = value
    save_user_settings(settings)
