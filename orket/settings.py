import json
from pathlib import Path
from typing import Dict, Any, Optional

SETTINGS_FILE = Path("user_settings.json")

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
    settings = load_user_settings()
    return settings.get(key, default)

def update_setting(key: str, value: Any):
    settings = load_user_settings()
    settings[key] = value
    save_user_settings(settings)
