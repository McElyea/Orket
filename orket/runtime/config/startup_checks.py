from __future__ import annotations

import logging
import os
from collections.abc import Mapping

LOCAL_ENVIRONMENT_NAMES = {"", "local", "localhost", "development", "dev", "test", "testing"}

REQUIRED_SECRET_PLACEHOLDERS: dict[str, set[str]] = {
    "ORKET_ENCRYPTION_KEY": {
        "your-32-byte-hex-key-here",
        "change-me-encryption-key",
    },
    "SESSION_SECRET": {
        "your-session-secret-here",
        "change-me-session-secret",
    },
    "GITEA_WEBHOOK_SECRET": {
        "change-me-webhook-secret",
        "your-webhook-secret-here",
    },
    "ORKET_API_KEY": {
        "change-me-api-key",
        "your-api-key-here",
    },
}


class StartupConfigurationError(RuntimeError):
    """Raised when a non-local runtime would start with unsafe placeholder secrets."""


def _env_value(env: Mapping[str, str] | None, name: str) -> str:
    source = os.environ if env is None else env
    return str(source.get(name, "") or "").strip()


def is_local_environment(env: Mapping[str, str] | None = None) -> bool:
    environment = _env_value(env, "ORKET_ENV").lower()
    return environment in LOCAL_ENVIRONMENT_NAMES


def validate_required_secrets(env: Mapping[str, str] | None = None) -> None:
    """Fail closed when a non-local environment uses missing or placeholder secrets."""
    if is_local_environment(env):
        return

    unsafe_names: list[str] = []
    for name, placeholders in REQUIRED_SECRET_PLACEHOLDERS.items():
        value = _env_value(env, name)
        if not value or value.lower() in placeholders:
            unsafe_names.append(name)

    if unsafe_names:
        joined = ", ".join(sorted(unsafe_names))
        raise StartupConfigurationError(
            f"Unsafe startup configuration for non-local ORKET_ENV: replace required secret(s): {joined}."
        )


def warn_if_insecure_gitea_https(
    env: Mapping[str, str] | None = None,
    *,
    logger: logging.Logger | None = None,
) -> bool:
    source = os.environ if env is None else env
    allow_insecure = str(source.get("ORKET_GITEA_ALLOW_INSECURE", "") or "").strip().lower()
    gitea_url = str(source.get("GITEA_URL", "") or "").strip()
    should_warn = allow_insecure in {"1", "true", "yes", "on"} and gitea_url.lower().startswith("https://")
    if should_warn:
        (logger or logging.getLogger(__name__)).warning(
            "orket_gitea_insecure_tls_bypass_on_https",
            extra={
                "config_key": "ORKET_GITEA_ALLOW_INSECURE",
                "gitea_url_scheme": "https",
            },
        )
    return should_warn
