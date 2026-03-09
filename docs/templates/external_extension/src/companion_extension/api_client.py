from __future__ import annotations

from typing import Any

import httpx


class CompanionApiClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def chat(self, *, session_id: str, message: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/api/v1/companion/chat",
                json={"session_id": session_id, "message": message},
            )
            response.raise_for_status()
            return response.json()
