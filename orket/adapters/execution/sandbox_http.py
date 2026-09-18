"""Side-effecting HTTP transport for already captured sandbox requests."""
from __future__ import annotations

import httpx

from orket.core.contracts.protocol_hashing import canonical_json
from orket.core.domain.sandbox_verifier import SandboxHttpObservation, SandboxHttpRequest
from orket_extension_sdk import FrozenJson

side_effecting = True


class SandboxHttpAdapter:
    def __init__(self, timeout_s: float):
        self.client = httpx.AsyncClient(timeout=timeout_s, trust_env=False)

    async def __aenter__(self) -> SandboxHttpAdapter:
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *args):
        return await self.client.__aexit__(*args)

    async def observe(self, request: SandboxHttpRequest) -> SandboxHttpObservation:
        response = None
        try:
            response = await self.client.request(request.method, request.url, json=request.payload.thaw())
            body = response.json() if "application/json" in response.headers.get("content-type", "").lower() else response.text
            return SandboxHttpObservation(request.scenario_id, response.status_code, FrozenJson(canonical_json(body)))
        except (httpx.HTTPError, httpx.InvalidURL, ValueError, TypeError, OSError) as exc:
            return SandboxHttpObservation(
                request.scenario_id, response.status_code if response is not None else None,
                error=f"E_SANDBOX_HTTP_OBSERVATION:{type(exc).__name__}",
            )
