import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.runtime_paths import resolve_user_settings_path, resolve_user_preferences_path

SETTINGS_FILE = resolve_user_settings_path(create_parent=False, migrate_legacy=False)
PREFERENCES_FILE = resolve_user_preferences_path(create_parent=False)
ENV_FILE = Path(".env")
_SETTINGS_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_META_KEY = "_meta"
_PREFERENCES_MIGRATION_MARKERS_KEY = "migration_markers"
_LEGACY_MODEL_PREFERENCES_MIGRATION_KEY = "legacy_model_preferences_v1"


def set_settings_file(path: Path):
    global SETTINGS_FILE, _SETTINGS_CACHE
    SETTINGS_FILE = resolve_user_settings_path(path)
    _SETTINGS_CACHE = None


def set_preferences_file(path: Path):
    global PREFERENCES_FILE, _PREFERENCES_CACHE
    PREFERENCES_FILE = resolve_user_preferences_path(path)
    _PREFERENCES_CACHE = None


def load_env():
    """Simple .env loader to avoid extra dependencies."""
    # Keep tests hermetic: avoid re-injecting host .env values after monkeypatch.delenv.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    if ENV_FILE.exists():
        fs = AsyncFileTools(Path("."))
        for line in fs.read_file_sync(str(ENV_FILE)).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, OSError):
        return {}
    return {}


def _default_settings_file() -> Path:
    return resolve_user_settings_path(create_parent=False, migrate_legacy=False)


def _default_preferences_file() -> Path:
    return resolve_user_preferences_path(create_parent=False)


def _settings_file_for_read() -> Path:
    if SETTINGS_FILE == _default_settings_file():
        return resolve_user_settings_path(create_parent=False, migrate_legacy=True)
    return SETTINGS_FILE


def _settings_file_for_write() -> Path:
    if SETTINGS_FILE == _default_settings_file():
        return resolve_user_settings_path(create_parent=True, migrate_legacy=True)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    return SETTINGS_FILE


def _preferences_file_for_read() -> Path:
    if PREFERENCES_FILE == _default_preferences_file():
        return resolve_user_preferences_path(create_parent=False)
    return PREFERENCES_FILE


def _preferences_file_for_write() -> Path:
    if PREFERENCES_FILE == _default_preferences_file():
        return resolve_user_preferences_path(create_parent=True)
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    return PREFERENCES_FILE


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
    if legacy != SETTINGS_FILE:
        search_paths.append(legacy)

    for settings_path in search_paths:
        if settings_path.exists():
            try:
                with settings_path.open("r", encoding="utf-8") as f:
                    _SETTINGS_CACHE = json.load(f)
                    return _SETTINGS_CACHE
            except (json.JSONDecodeError, OSError):
                return {}
    return {}


def save_user_settings(settings: Dict[str, Any]):
    """Saves settings to the project root and updates cache."""
    global _SETTINGS_CACHE
    settings_path = _settings_file_for_write()
    with settings_path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)
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


def save_user_preferences(preferences: Dict[str, Any]):
    """Saves preference settings and updates cache."""
    global _PREFERENCES_CACHE
    preferences_path = _preferences_file_for_write()
    with preferences_path.open("w", encoding="utf-8") as f:
        json.dump(preferences, f, indent=4)
    _PREFERENCES_CACHE = preferences


def migrate_legacy_model_preferences() -> Dict[str, Any]:
    """
    Hard migration: move legacy preferred_* model keys out of user_settings.json
    into preferences.json under {"models": {"<role>": "<model>"}}.
    """
    global _SETTINGS_CACHE, _PREFERENCES_CACHE

    settings = load_user_settings().copy()
    preferences = _read_json(_preferences_file_for_read())
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
