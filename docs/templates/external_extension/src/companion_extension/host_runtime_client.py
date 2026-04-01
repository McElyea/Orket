from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class HostRuntimeClient:
    def __init__(
        self,
        base_url: str,
        *,
        extension_id: str,
        timeout_seconds: float = 30.0,
        api_key: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._extension_id = str(extension_id or "").strip()
        self._timeout = timeout_seconds
        self._api_key = api_key.strip()

    async def status(self) -> dict[str, Any]:
        return await self._request("GET", self._path("/status"))

    async def models(self, *, provider: str = "ollama") -> dict[str, Any]:
        normalized = str(provider or "").strip().lower() or "ollama"
        return await self._request("GET", self._path("/models"), params={"provider": normalized})

    async def llm_generate(
        self,
        *,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 256,
        temperature: float = 0.2,
        stop_sequences: list[str] | None = None,
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/llm/generate"),
            json={
                "system_prompt": system_prompt,
                "user_message": user_message,
                "max_tokens": int(max_tokens),
                "temperature": float(temperature),
                "stop_sequences": list(stop_sequences or []),
                "provider": provider,
                "model": model,
            },
        )

    async def memory_query(
        self,
        *,
        scope: str,
        session_id: str = "",
        query: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/memory/query"),
            json={
                "scope": scope,
                "session_id": session_id,
                "query": query,
                "limit": int(limit),
            },
        )

    async def memory_write(
        self,
        *,
        scope: str,
        key: str,
        value: str,
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/memory/write"),
            json={
                "scope": scope,
                "key": key,
                "value": value,
                "session_id": session_id,
                "metadata": dict(metadata or {}),
            },
        )

    async def memory_clear(self, *, scope: str, session_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/memory/clear"),
            json={"scope": scope, "session_id": session_id},
        )

    async def voice_state(self) -> dict[str, Any]:
        return await self._request("GET", self._path("/voice/state"))

    async def voice_control(self, *, command: str, silence_delay_sec: float | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"command": command}
        if silence_delay_sec is not None:
            payload["silence_delay_sec"] = silence_delay_sec
        return await self._request("POST", self._path("/voice/control"), json=payload)

    async def voice_transcribe(
        self,
        *,
        audio_b64: str,
        mime_type: str = "audio/wav",
        language_hint: str = "",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/voice/transcribe"),
            json={"audio_b64": audio_b64, "mime_type": mime_type, "language_hint": language_hint},
        )

    async def voice_voices(self) -> dict[str, Any]:
        return await self._request("GET", self._path("/tts/voices"))

    async def voice_synthesize(
        self,
        *,
        text: str,
        voice_id: str = "",
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            self._path("/tts/synthesize"),
            json={
                "text": text,
                "voice_id": voice_id,
                "emotion_hint": emotion_hint,
                "speed": float(speed),
            },
        )

    def _path(self, suffix: str) -> str:
        return f"/v1/extensions/{quote(self._extension_id, safe='')}/runtime{suffix}"

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
