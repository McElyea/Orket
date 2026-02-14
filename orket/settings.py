import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.runtime_paths import resolve_user_settings_path

SETTINGS_FILE = resolve_user_settings_path()
ENV_FILE = Path(".env")
_SETTINGS_CACHE: Optional[Dict[str, Any]] = None

def set_settings_file(path: Path):
    global SETTINGS_FILE, _SETTINGS_CACHE
    SETTINGS_FILE = resolve_user_settings_path(path)
    _SETTINGS_CACHE = None # Invalidate cache on path change

def load_env():
    """Simple .env loader to avoid extra dependencies."""
    if ENV_FILE.exists():
        fs = AsyncFileTools(Path("."))
        for line in fs.read_file_sync(str(ENV_FILE)).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

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

