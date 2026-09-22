"""HTTP effects for an explicitly authorized Gitea endpoint and credential pair."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from orket.core.contracts.provider_http import CapturedHttpClientPort

logger = logging.getLogger(__name__)
side_effecting = True


def validate_gitea_url(gitea_url: str, *, allow_insecure: bool) -> str:
    resolved = str(gitea_url or "").strip().rstrip("/")
    parsed = urlparse(resolved)
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Gitea URL requires a host and must not contain embedded credentials, query or fragment.")
    if parsed.scheme.lower() == "https":
        return resolved
    if parsed.scheme.lower() == "http" and allow_insecure:
        logger.warning("gitea_webhook_insecure_url_allowed")
        return resolved
    raise ValueError("Gitea webhook handler requires an https:// gitea_url unless allow_insecure=True.")


def build_webhook_http_client(*, username: str, password: str,
                              http_client_owner: CapturedHttpClientPort) -> httpx.AsyncClient:
    # Construction owns a connection pool; the application must close it after admitted work settles.
    return http_client_owner.create_client(auth=(username, password), timeout_s=10.0)
