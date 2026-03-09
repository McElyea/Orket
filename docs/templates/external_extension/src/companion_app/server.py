from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from companion_extension.api_client import CompanionApiClient


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    provider: str = ""
    model: str = ""


class ConfigUpdateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    scope: str = Field(default="next_turn", min_length=1)
    patch: dict[str, Any] = Field(default_factory=dict)


class VoiceControlRequest(BaseModel):
    command: str = Field(min_length=1)
    silence_delay_sec: float | None = None


class TranscribeRequest(BaseModel):
    audio_b64: str = Field(min_length=1)
    mime_type: str = Field(default="audio/wav", min_length=1)
    language_hint: str = ""


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str = ""
    emotion_hint: str = "neutral"
    speed: float = 1.0


class CadenceSuggestRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class SessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


app = FastAPI(title="Companion Template")
_STATIC_ROOT = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_ROOT), name="static")


def _client() -> CompanionApiClient:
    base_url = str(os.getenv("COMPANION_HOST_BASE_URL", "http://127.0.0.1:8000")).strip()
    api_key = str(os.getenv("COMPANION_API_KEY", "")).strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "code": "E_COMPANION_GATEWAY_API_KEY_REQUIRED",
                "message": "COMPANION_API_KEY is required for Companion host API access.",
            },
        )
    timeout_seconds = float(os.getenv("COMPANION_TIMEOUT_SECONDS", "45"))
    return CompanionApiClient(base_url, timeout_seconds=timeout_seconds, api_key=api_key)


def _raise_gateway_error(exc: httpx.HTTPError) -> None:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = int(exc.response.status_code)
        detail: Any
        try:
            detail = exc.response.json()
        except ValueError:
            detail = exc.response.text
        raise HTTPException(status_code=status_code, detail=detail) from exc
    raise HTTPException(status_code=502, detail=f"Host API request failed: {exc}") from exc


@app.get("/", response_class=FileResponse)
async def home() -> FileResponse:
    return FileResponse(_STATIC_ROOT / "index.html")


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/status")
async def status() -> dict[str, Any]:
    try:
        return await _client().status()
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.get("/api/config")
async def get_config(session_id: str) -> dict[str, Any]:
    try:
        return await _client().get_config(session_id=session_id)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.patch("/api/config")
async def update_config(req: ConfigUpdateRequest) -> dict[str, Any]:
    try:
        return await _client().update_config(session_id=req.session_id, scope=req.scope, patch=req.patch)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.get("/api/history")
async def history(session_id: str, limit: int = 50) -> dict[str, Any]:
    try:
        return await _client().history(session_id=session_id, limit=limit)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    try:
        return await _client().chat(
            session_id=req.session_id,
            message=req.message,
            provider=req.provider,
            model=req.model,
        )
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/session/clear-memory")
async def clear_memory(req: SessionRequest) -> dict[str, Any]:
    try:
        return await _client().clear_session_memory(session_id=req.session_id)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.get("/api/voice/state")
async def voice_state() -> dict[str, Any]:
    try:
        return await _client().voice_state()
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.get("/api/voice/voices")
async def voice_voices() -> dict[str, Any]:
    try:
        return await _client().voice_voices()
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/control")
async def voice_control(req: VoiceControlRequest) -> dict[str, Any]:
    try:
        return await _client().voice_control(command=req.command, silence_delay_sec=req.silence_delay_sec)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/transcribe")
async def voice_transcribe(req: TranscribeRequest) -> dict[str, Any]:
    try:
        return await _client().voice_transcribe(
            audio_b64=req.audio_b64,
            mime_type=req.mime_type,
            language_hint=req.language_hint,
        )
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/synthesize")
async def voice_synthesize(req: SynthesizeRequest) -> dict[str, Any]:
    try:
        return await _client().voice_synthesize(
            text=req.text,
            voice_id=req.voice_id,
            emotion_hint=req.emotion_hint,
            speed=req.speed,
        )
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/cadence/suggest")
async def voice_cadence_suggest(req: CadenceSuggestRequest) -> dict[str, Any]:
    try:
        return await _client().voice_cadence_suggest(session_id=req.session_id, text=req.text)
    except httpx.HTTPError as exc:
        _raise_gateway_error(exc)
