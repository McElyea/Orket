from __future__ import annotations

import os
from typing import Any, Dict, List


REQUIRED_CONFIG_KEYS = [
    "gitea_url",
    "gitea_token",
    "gitea_owner",
    "gitea_repo",
]


def collect_gitea_state_pilot_inputs() -> Dict[str, Any]:
    def _env(name: str) -> str:
        return str(os.environ.get(name) or "").strip()

    return {
        "state_backend_mode": _env("ORKET_STATE_BACKEND_MODE") or "local",
        "pilot_enabled": _env("ORKET_ENABLE_GITEA_STATE_PILOT").lower() in {"1", "true", "yes", "on"},
        "gitea_url": _env("ORKET_GITEA_URL"),
        "gitea_token": _env("ORKET_GITEA_TOKEN"),
        "gitea_owner": _env("ORKET_GITEA_OWNER"),
        "gitea_repo": _env("ORKET_GITEA_REPO"),
    }


def evaluate_gitea_state_pilot_readiness(inputs: Dict[str, Any]) -> Dict[str, Any]:
    failures: List[str] = []
    mode = str(inputs.get("state_backend_mode") or "").strip().lower()
    pilot_enabled = bool(inputs.get("pilot_enabled"))
    if mode != "gitea":
        failures.append(f"state_backend_mode must be 'gitea' (got '{mode or 'unset'}')")
    if not pilot_enabled:
        failures.append("ORKET_ENABLE_GITEA_STATE_PILOT must be enabled")

    missing = [
        key
        for key in REQUIRED_CONFIG_KEYS
        if not str(inputs.get(key) or "").strip()
    ]
    if missing:
        failures.append(f"missing required gitea config: {', '.join(missing)}")

    return {
        "ready": len(failures) == 0,
        "state_backend_mode": mode or "local",
        "pilot_enabled": pilot_enabled,
        "missing_config_keys": missing,
        "failures": failures,
    }
