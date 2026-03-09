from __future__ import annotations

import json
from pathlib import Path

from .config_schema import CompanionDefaults


def load_defaults(config_root: Path | None = None) -> CompanionDefaults:
    root = Path(config_root or Path(__file__).resolve().parents[2] / "config").resolve()
    defaults_path = root / "defaults.json"
    payload = json.loads(defaults_path.read_text(encoding="utf-8"))
    return CompanionDefaults.model_validate(payload)
