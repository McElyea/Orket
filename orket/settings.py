import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

SETTINGS_FILE = Path("user_settings.json")
ENV_FILE = Path(".env")

def set_settings_file(path: Path):
    global SETTINGS_FILE
    SETTINGS_FILE = path

def load_env():
    """Simple .env loader to avoid extra dependencies."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

# Load environment variables on module import
load_env()

def load_user_settings() -> Dict[str, Any]:
    """Loads settings from the project root."""
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_settings(settings: Dict[str, Any]):
    """Saves settings to the project root."""
    with SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

def get_setting(key: str, default: Any = None) -> Any:
    # Check environment first (UPPERCASE)
    env_val = os.environ.get(key.upper())
    if env_val is not None:
        return env_val
        
    settings = load_user_settings()
    return settings.get(key, default)

def update_setting(key: str, value: Any):
    settings = load_user_settings()
    settings[key] = value
    save_user_settings(settings)
