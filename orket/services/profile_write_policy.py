from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_PROFILE_KEY_PREFIXES: tuple[str, ...] = (
    "user_preference.",
    "user_fact.",
    "companion_setting.",
    "companion_mode.",
)


@dataclass(frozen=True)
class ProfileWritePolicyError(ValueError):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ProfileWritePolicy:
    def __init__(self, *, allowed_prefixes: tuple[str, ...] = ALLOWED_PROFILE_KEY_PREFIXES) -> None:
        self._allowed_prefixes = tuple(str(prefix).strip() for prefix in allowed_prefixes if str(prefix).strip())

    def validate(self, *, key: str, metadata: dict[str, Any] | None) -> None:
        key_name = str(key or "").strip()
        if not key_name:
            raise ProfileWritePolicyError(
                code="E_PROFILE_MEMORY_KEY_REQUIRED",
                message="Profile memory writes require a non-empty key.",
            )
        if not any(key_name.startswith(prefix) for prefix in self._allowed_prefixes):
            raise ProfileWritePolicyError(
                code="E_PROFILE_MEMORY_KEY_FORBIDDEN",
                message=f"Profile memory key '{key_name}' is outside the allowed prefix policy.",
            )
        payload = dict(metadata or {})
        if key_name.startswith("user_fact.") and not bool(payload.get("user_confirmed")):
            raise ProfileWritePolicyError(
                code="E_PROFILE_MEMORY_CONFIRMATION_REQUIRED",
                message=f"Profile memory key '{key_name}' requires metadata.user_confirmed=true.",
            )
