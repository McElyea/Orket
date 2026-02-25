from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


DEFAULT_NETWORK_MODE = "offline"
KNOWN_NETWORK_MODES = {"offline", "online_opt_in"}

OFFLINE_CAPABILITY_MATRIX: Dict[str, Dict[str, Any]] = {
    "init": {
        "offline_supported": True,
        "requires_network": False,
        "degradation": "none",
        "notes": "Uses local blueprint hydration only in v1.",
    },
    "api_add": {
        "offline_supported": True,
        "requires_network": False,
        "degradation": "none",
        "notes": "Uses local project files and local verify commands.",
    },
    "refactor": {
        "offline_supported": True,
        "requires_network": False,
        "degradation": "none",
        "notes": "Uses local repository and local verification profile.",
    },
}


@dataclass(frozen=True)
class OfflineModeError(Exception):
    code: str
    message: str
    detail: Dict[str, Any]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "ok": False,
            "code": self.code,
            "message": self.message,
            "detail": dict(self.detail),
        }


def resolve_network_mode(*values: Any) -> str:
    for raw in values:
        normalized = str(raw or "").strip().lower()
        if not normalized:
            continue
        if normalized not in KNOWN_NETWORK_MODES:
            raise OfflineModeError(
                code="E_NETWORK_MODE_INVALID",
                message=f"Unknown network mode '{normalized}'.",
                detail={"mode": normalized, "known_modes": sorted(KNOWN_NETWORK_MODES)},
            )
        return normalized
    return DEFAULT_NETWORK_MODE


def command_offline_capability(command_name: str) -> Dict[str, Any]:
    key = str(command_name or "").strip().lower()
    row = OFFLINE_CAPABILITY_MATRIX.get(key)
    if not isinstance(row, dict):
        raise OfflineModeError(
            code="E_OFFLINE_COMMAND_UNKNOWN",
            message=f"Unknown command in offline matrix: '{key}'.",
            detail={"command": key, "known_commands": sorted(OFFLINE_CAPABILITY_MATRIX.keys())},
        )
    return dict(row)


def assert_default_offline_surface(required_commands: List[str] | None = None) -> None:
    required = required_commands or ["init", "api_add", "refactor"]
    for command in required:
        row = command_offline_capability(command)
        if not bool(row.get("offline_supported")):
            raise OfflineModeError(
                code="E_OFFLINE_UNSUPPORTED_COMMAND",
                message=f"Command '{command}' must support offline mode.",
                detail={"command": command, "row": row},
            )
        if bool(row.get("requires_network")):
            raise OfflineModeError(
                code="E_OFFLINE_DEFAULT_NETWORK_REQUIRED",
                message=f"Command '{command}' requires network by default.",
                detail={"command": command, "row": row},
            )
