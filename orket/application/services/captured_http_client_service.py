"""Captured HTTPX composition reuses provider network policy and resource ownership."""
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from orket.adapters.llm.provider_catalog_client import build_provider_http_client
from orket.application.services.provider_http_resources import ProviderHttpResources
from orket.application.services.provider_http_service import capture_provider_http_inputs


class CapturedHttpClientService:
    def __init__(self, *, environment: Mapping[str, str], cwd: Path):
        self._inputs = capture_provider_http_inputs(environment=environment, cwd=cwd)
        self._resources = ProviderHttpResources()

    def create_client(self, *, timeout_s: float, auth: tuple[str, str] | None = None) -> Any:
        budget = float(timeout_s)
        if not math.isfinite(budget):
            raise ValueError("E_HTTP_CLIENT_TIMEOUT_NOT_FINITE")
        return build_provider_http_client(inputs=self._inputs, factory=httpx.AsyncClient,
            options=dict(timeout=budget, auth=auth, follow_redirects=False), own_resource=self._resources.retain)

    async def close(self, client: Any = None) -> None:
        await self._resources.close(client)
