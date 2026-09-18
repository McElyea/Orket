"""Capture standalone webhook startup inputs before constructing runtime owners."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _positive_integer(value: str | None, default: int) -> int:
    try:
        return max(1, int(value or default))
    except ValueError:
        return default


@dataclass(frozen=True)
class WebhookConfiguration:
    project_root: Path
    invocation_root: Path
    environment: Mapping[str, str] = field(repr=False)
    gitea_url: str
    user: str
    password: str = field(repr=False)
    secret: bytes = field(repr=False)
    test_token: str = field(repr=False)
    api_key: str = field(repr=False)
    test_enabled: bool
    allow_insecure: bool
    rate_limit: int
    worker_count: int


def capture_webhook_configuration(
    project_root: Path | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    require_config: bool = True,
) -> WebhookConfiguration:
    if require_config and environment is None:
        from orket.settings import load_env

        load_env()
    observed = MappingProxyType(dict(os.environ if environment is None else environment))
    missing = [name for name in ("GITEA_WEBHOOK_SECRET", "GITEA_ADMIN_PASSWORD") if not observed.get(name, "").strip()]
    if require_config and missing:
        raise RuntimeError(
            "Missing required webhook environment variable(s): "
            + ", ".join(missing)
            + ". Configure them in environment or .env before starting the webhook server."
        )
    invocation = Path.cwd().resolve()
    return WebhookConfiguration(
        project_root=Path(project_root or invocation).resolve(),
        invocation_root=invocation,
        environment=observed,
        gitea_url=observed.get("GITEA_URL", "https://localhost:3000"),
        user=observed.get("GITEA_ADMIN_USER", "Orket"),
        password=observed.get("GITEA_ADMIN_PASSWORD", ""),
        secret=observed.get("GITEA_WEBHOOK_SECRET", "").encode(),
        test_token=observed.get("ORKET_WEBHOOK_TEST_TOKEN", "").strip(),
        api_key=observed.get("ORKET_API_KEY", "").strip(),
        test_enabled=_enabled(observed.get("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT")),
        allow_insecure=_enabled(observed.get("ORKET_GITEA_ALLOW_INSECURE")),
        rate_limit=_positive_integer(observed.get("ORKET_RATE_LIMIT"), 60),
        worker_count=_positive_integer(observed.get("ORKET_WEBHOOK_WORKERS") or observed.get("WEB_CONCURRENCY"), 1),
    )
