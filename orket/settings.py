import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from orket.infrastructure.async_file_tools import AsyncFileTools

SETTINGS_FILE = Path("user_settings.json")
ENV_FILE = Path(".env")
_SETTINGS_CACHE: Optional[Dict[str, Any]] = None

def set_settings_file(path: Path):
    global SETTINGS_FILE, _SETTINGS_CACHE
    SETTINGS_FILE = path
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

    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as f:
                _SETTINGS_CACHE = json.load(f)
                return _SETTINGS_CACHE
        except Exception:
            return {}
    return {}

def save_user_settings(settings: Dict[str, Any]):
    """Saves settings to the project root and updates cache."""
    global _SETTINGS_CACHE
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
