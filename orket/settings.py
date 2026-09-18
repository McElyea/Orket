"""Captured runtime settings and application-owned persistent settings access."""
from __future__ import annotations

import asyncio
import contextvars
import json
import os
import threading
from collections.abc import Coroutine, Mapping
from pathlib import Path
from typing import Any, TypeVar

from dotenv import dotenv_values

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.user_settings_service import SettingsLocation, UserSettingsService
from orket.exceptions import SettingsBridgeError

ENV_FILE = Path(".env")
_SETTINGS_FILE: Path | None = None
_PREFERENCES_FILE: Path | None = None
_ENV_LOADED = False
_ENV_LOADED_LOCK = threading.Lock()
ResultT = TypeVar("ResultT")
_RUNTIME_USER_SETTINGS: contextvars.ContextVar[str | None] = contextvars.ContextVar("runtime_user_settings", default=None)
_RUNTIME_USER_PREFERENCES: contextvars.ContextVar[str | None] = contextvars.ContextVar("runtime_user_preferences", default=None)
_RUNTIME_ENVIRONMENT: contextvars.ContextVar[tuple[tuple[str, str], ...] | None] = contextvars.ContextVar(
    "runtime_settings_environment", default=None,
)


def _capture_location() -> SettingsLocation:
    return SettingsLocation(Path.cwd(), os.environ.get("ORKET_DURABLE_ROOT", ""), _SETTINGS_FILE, _PREFERENCES_FILE)


def _encode(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("E_SETTINGS_OBJECT_REQUIRED")
    return json.dumps(payload, allow_nan=False)


def set_settings_file(path: Path) -> None:
    global _SETTINGS_FILE
    _SETTINGS_FILE = Path(path).absolute()
    _RUNTIME_USER_SETTINGS.set(None)


def set_preferences_file(path: Path) -> None:
    global _PREFERENCES_FILE
    _PREFERENCES_FILE = Path(path).absolute()
    _RUNTIME_USER_PREFERENCES.set(None)


def _is_running_in_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


def _run_settings_sync(awaitable: Coroutine[Any, Any, ResultT], *, operation: str) -> ResultT:
    """Explicit bootstrap bridge; never inspect files to decide event-loop admission."""
    if _is_running_in_event_loop():
        awaitable.close()
        raise SettingsBridgeError(
            f"{operation} must run before the event loop starts or after set_runtime_settings_context()."
        )
    return asyncio.run(awaitable)


def set_runtime_settings_context(
    *, user_settings: dict[str, Any] | None = None, user_preferences: dict[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
) -> None:
    # Serialize both values before publication: a bad second value cannot partially bind a context.
    settings = _encode(user_settings) if user_settings is not None else None
    preferences = _encode(user_preferences) if user_preferences is not None else None
    captured_environment = tuple((os.environ if environment is None else environment).items())
    if settings is not None:
        _RUNTIME_USER_SETTINGS.set(settings)
    if preferences is not None:
        _RUNTIME_USER_PREFERENCES.set(preferences)
    _RUNTIME_ENVIRONMENT.set(captured_environment)


def clear_runtime_settings_context() -> None:
    _RUNTIME_USER_SETTINGS.set(None)
    _RUNTIME_USER_PREFERENCES.set(None)
    _RUNTIME_ENVIRONMENT.set(None)


def clear_settings_cache() -> None:
    """Reset explicit bootstrap selections/context; persistent data has no implicit cache."""
    global _SETTINGS_FILE, _PREFERENCES_FILE, _ENV_LOADED
    _SETTINGS_FILE = None
    _PREFERENCES_FILE = None
    clear_runtime_settings_context()
    with _ENV_LOADED_LOCK:
        _ENV_LOADED = False


def load_env() -> None:
    """Load the selected .env once, at an explicit synchronous bootstrap boundary."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    if _is_running_in_event_loop():
        raise SettingsBridgeError("load_env must run before the event loop starts.")
    with _ENV_LOADED_LOCK:
        if _ENV_LOADED:
            return
        for key, value in dotenv_values(ENV_FILE).items():
            if key and value is not None:
                os.environ.setdefault(str(key).strip(), str(value))
        _ENV_LOADED = True


async def load_user_settings_async() -> dict[str, Any]:
    """Observe persistence at the captured invocation/selection, independently of runtime snapshots."""
    location = _capture_location()
    return await run_owned_thread(lambda: UserSettingsService(location).read_settings(), label="settings-read")


def load_user_settings() -> dict[str, Any]:
    snapshot = _RUNTIME_USER_SETTINGS.get()
    if snapshot is not None:
        return json.loads(snapshot)
    return _run_settings_sync(load_user_settings_async(), operation="load_user_settings")


async def save_user_settings_async(
    settings: dict[str, Any], *, expected: dict[str, Any] | None = None,
) -> None:
    location, captured = _capture_location(), _encode(settings)
    expected_json = _encode(expected) if expected is not None else None
    await run_owned_thread(lambda: UserSettingsService(location).save(
        json.loads(captured), preferences=False,
        expected_settings=json.loads(expected_json) if expected_json is not None else None,
    ), label="settings-write")


def save_user_settings(settings: dict[str, Any], *, expected: dict[str, Any] | None = None) -> None:
    _run_settings_sync(save_user_settings_async(settings, expected=expected), operation="save_user_settings")


async def save_user_preferences_async(preferences: dict[str, Any]) -> None:
    location, captured = _capture_location(), _encode(preferences)
    await run_owned_thread(lambda: UserSettingsService(location).save(json.loads(captured), preferences=True),
                           label="preferences-write")


def save_user_preferences(preferences: dict[str, Any]) -> None:
    _run_settings_sync(save_user_preferences_async(preferences), operation="save_user_preferences")


async def migrate_legacy_model_preferences_async() -> dict[str, Any]:
    location = _capture_location()
    return await run_owned_thread(lambda: UserSettingsService(location).read_preferences(), label="preferences-migration")


def migrate_legacy_model_preferences() -> dict[str, Any]:
    return _run_settings_sync(migrate_legacy_model_preferences_async(), operation="migrate_legacy_model_preferences")


async def load_user_preferences_async() -> dict[str, Any]:
    return await migrate_legacy_model_preferences_async()


def load_user_preferences() -> dict[str, Any]:
    snapshot = _RUNTIME_USER_PREFERENCES.get()
    if snapshot is not None:
        return json.loads(snapshot)
    return _run_settings_sync(load_user_preferences_async(), operation="load_user_preferences")


def get_setting(key: str, default: Any = None) -> Any:
    snapshot = _RUNTIME_ENVIRONMENT.get()
    environment = os.environ if snapshot is None else dict(snapshot)
    env_val = environment.get(key.upper())
    return env_val if env_val is not None else load_user_settings().get(key, default)


def update_setting(key: str, value: Any) -> None:
    captured = _encode({key: value})
    location = _capture_location()

    async def update() -> None:
        await run_owned_thread(lambda: UserSettingsService(location).update(key, json.loads(captured)[key]),
                               label="settings-update")

    _run_settings_sync(update(), operation="update_setting")
