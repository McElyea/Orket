"""Application-owned API authentication over captured startup inputs."""
from __future__ import annotations

import hmac
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from orket.runtime.config.startup_checks import validate_required_secrets, warn_if_insecure_gitea_https


@dataclass(frozen=True)
class ApiAuthenticationService:
    environment: Mapping[str, str] = field(repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "environment", MappingProxyType(dict(self.environment)))

    @property
    def key_configured(self) -> bool:
        return bool(self.environment.get("ORKET_API_KEY", "").strip())

    @property
    def insecure_bypass(self) -> bool:
        return self.environment.get("ORKET_ALLOW_INSECURE_NO_API_KEY", "").strip().lower() in {
            "1", "true", "yes", "on",
        }

    def validate_startup(self, logger: logging.Logger) -> None:
        self.enforce_insecure_bypass_policy(logger)
        validate_required_secrets(self.environment)
        warn_if_insecure_gitea_https(self.environment, logger=logger)

    def enforce_insecure_bypass_policy(self, logger: logging.Logger) -> bool:
        if not self.insecure_bypass:
            return False
        logger.critical("orket_insecure_no_api_key_enabled", extra={
            "warning": "API authentication is disabled. Never set this in non-local environments.",
        })
        if self.environment.get("ORKET_ENV", "").strip().lower() in {"production", "staging"}:
            raise RuntimeError("ORKET_ALLOW_INSECURE_NO_API_KEY is forbidden when ORKET_ENV is production or staging.")
        return True

    def authenticate(self, provided_key: str | None) -> bool:
        expected = self.environment.get("ORKET_API_KEY", "").strip()
        if expected:
            return hmac.compare_digest(str(provided_key or ""), expected)
        profile = self.environment.get("ORKET_API_SECURITY_PROFILE", "production").strip().lower() or "production"
        nonlocal_environment = self.environment.get("ORKET_ENV", "").strip().lower() in {"production", "staging"}
        return profile != "production" and self.insecure_bypass and not nonlocal_environment

    def websocket_key(self, header_key: str | None, query_key: str | None) -> str | None:
        mode = self.environment.get("ORKET_API_SECURITY_MODE", "compat").strip().lower() or "compat"
        return header_key or (query_key if mode != "enforce" else None)

    def query_warning(self, query_key_used: bool, *, input_ref: str, timestamp_utc: str) -> dict[str, str] | None:
        mode = self.environment.get("ORKET_API_SECURITY_MODE", "compat").strip().lower() or "compat"
        if not query_key_used or mode != "compat":
            return None
        return {"event_name": "security_compat_fallback_used", "component": "api.websocket_auth",
                "fallback_code": "API_QUERY_AUTH_COMPAT", "mode": mode, "reason": "query_auth_used",
                "input_ref": input_ref, "timestamp_utc": timestamp_utc}
