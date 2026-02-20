import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.runtime_paths import resolve_user_settings_path, resolve_user_preferences_path

SETTINGS_FILE = resolve_user_settings_path()
PREFERENCES_FILE = resolve_user_preferences_path()
ENV_FILE = Path(".env")
_SETTINGS_CACHE: Optional[Dict[str, Any]] = None
_PREFERENCES_CACHE: Optional[Dict[str, Any]] = None


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


def load_user_settings() -> Dict[str, Any]:
    """Loads settings from the project root with caching."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE

    search_paths = [SETTINGS_FILE]
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
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
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
    PREFERENCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with PREFERENCES_FILE.open("w", encoding="utf-8") as f:
        json.dump(preferences, f, indent=4)
    _PREFERENCES_CACHE = preferences


def migrate_legacy_model_preferences() -> Dict[str, Any]:
    """
    Hard migration: move legacy preferred_* model keys out of user_settings.json
    into preferences.json under {"models": {"<role>": "<model>"}}.
    """
    global _SETTINGS_CACHE, _PREFERENCES_CACHE

    settings = load_user_settings().copy()
    legacy_models = _extract_legacy_model_preferences(settings)
    if not legacy_models:
        return _read_json(PREFERENCES_FILE)

    preferences = _read_json(PREFERENCES_FILE)
    existing_models = preferences.get("models")
    models = dict(existing_models) if isinstance(existing_models, dict) else {}
    for role, model in legacy_models.items():
        models[str(role).strip()] = model

    preferences["models"] = models
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

    migrate_legacy_model_preferences()
    _PREFERENCES_CACHE = _read_json(PREFERENCES_FILE)
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
