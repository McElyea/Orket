from __future__ import annotations

from typing import Any

import httpx


class CompanionApiClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0, api_key: str = "") -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._api_key = api_key.strip()

    async def status(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/companion/status")

    async def get_config(self, *, session_id: str) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/companion/config", params={"session_id": session_id})

    async def update_config(self, *, session_id: str, scope: str, patch: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            "/api/v1/companion/config",
            json={"session_id": session_id, "scope": scope, "patch": patch},
        )

    async def history(self, *, session_id: str, limit: int = 50) -> dict[str, Any]:
        return await self._request(
            "GET",
            "/api/v1/companion/history",
            params={"session_id": session_id, "limit": max(1, int(limit))},
        )

    async def chat(self, *, session_id: str, message: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/companion/chat",
            json={"session_id": session_id, "message": message},
        )

    async def clear_session_memory(self, *, session_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/companion/session/clear-memory",
            json={"session_id": session_id},
        )

    async def voice_state(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/companion/voice/state")

    async def voice_control(self, *, command: str, silence_delay_sec: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if silence_delay_sec is not None:
            payload["silence_delay_sec"] = silence_delay_sec
        return await self._request("POST", "/api/v1/companion/voice/control", json=payload)

    async def voice_transcribe(
        self,
        *,
        audio_b64: str,
        mime_type: str = "audio/wav",
        language_hint: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/api/v1/companion/voice/transcribe",
            json={"audio_b64": audio_b64, "mime_type": mime_type, "language_hint": language_hint},
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method=method,
                url=f"{self._base_url}{path}",
                headers=headers,
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()
