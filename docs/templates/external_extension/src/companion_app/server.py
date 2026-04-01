from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from companion_extension.api_client import CompanionApiClient


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)
    provider: str = Field(default="", max_length=64)
    model: str = Field(default="", max_length=128)


class ConfigUpdateRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    scope: str = Field(default="next_turn", min_length=1, max_length=32)
    patch: dict[str, Any] = Field(default_factory=dict)


class VoiceControlRequest(BaseModel):
    command: str = Field(min_length=1, max_length=32)
    silence_delay_sec: float | None = None


class TranscribeRequest(BaseModel):
    audio_b64: str = Field(min_length=1, max_length=8_000_000)
    mime_type: str = Field(default="audio/wav", min_length=1, max_length=128)
    language_hint: str = Field(default="", max_length=32)


class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice_id: str = Field(default="", max_length=128)
    emotion_hint: str = Field(default="neutral", max_length=64)
    speed: float = 1.0


class CadenceSuggestRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=4000)


class SessionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)


app = FastAPI(title="Companion Template")
_STATIC_ROOT = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=_STATIC_ROOT), name="static")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
_MUTATING_METHODS = frozenset({"POST", "PATCH", "PUT", "DELETE"})
_MAX_CONFIG_PATCH_BYTES = 20_000
_MAX_CHAT_MESSAGE_BYTES = 8_000
_MAX_AUDIO_B64_BYTES = 8_000_000
_MAX_SYNTH_TEXT_BYTES = 4_000
_MAX_CADENCE_TEXT_BYTES = 8_000
_DEFAULT_HOST_API_BASE_URL = "http://127.0.0.1:8082"
_DEFAULT_EXTENSION_ID = "orket.companion"
_HOST_API_KEY_ENV_NAMES = ("COMPANION_API_KEY", "ORKET_API_KEY")


def _flag_enabled(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _is_loopback_host(host: str) -> bool:
    return str(host or "").strip().lower() in _LOOPBACK_HOSTS


def _require_loopback_client(request: Request) -> None:
    if not _flag_enabled("COMPANION_GATEWAY_REQUIRE_LOOPBACK", default=True):
        return
    client_host = str(request.client.host if request.client else "").strip().lower()
    if _is_loopback_host(client_host):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "ok": False,
            "code": "E_COMPANION_GATEWAY_LOOPBACK_REQUIRED",
            "message": "Gateway requests must originate from a loopback client address.",
        },
    )


def _require_same_origin_for_mutation(request: Request) -> None:
    method = str(request.method or "").strip().upper()
    if method not in _MUTATING_METHODS:
        return
    if not _flag_enabled("COMPANION_GATEWAY_REQUIRE_SAME_ORIGIN", default=True):
        return
    origin = str(request.headers.get("origin", "")).strip().lower()
    expected_origin = f"{request.url.scheme}://{request.url.netloc}".lower()
    if origin == expected_origin:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "ok": False,
            "code": "E_COMPANION_GATEWAY_CSRF_BLOCKED",
            "message": "Mutation request origin must match the gateway origin.",
        },
    )


def _enforce_gateway_request_policy(request: Request) -> None:
    _require_loopback_client(request)
    _require_same_origin_for_mutation(request)


def _enforce_patch_size_limit(patch: dict[str, Any]) -> None:
    payload_bytes = len(json.dumps(patch, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    if payload_bytes <= _MAX_CONFIG_PATCH_BYTES:
        return
    raise HTTPException(
        status_code=413,
        detail={
            "ok": False,
            "code": "E_COMPANION_CONFIG_PATCH_TOO_LARGE",
            "message": f"Config patch exceeds {_MAX_CONFIG_PATCH_BYTES} bytes.",
        },
    )


def _enforce_text_size_limit(*, value: str, max_bytes: int, code: str, message: str) -> None:
    payload_bytes = len(str(value or "").encode("utf-8"))
    if payload_bytes <= max_bytes:
        return
    raise HTTPException(
        status_code=413,
        detail={
            "ok": False,
            "code": code,
            "message": message,
        },
    )


def _read_first_nonempty_env(*names: str) -> str:
    for name in names:
        value = str(os.getenv(name, "")).strip()
        if value:
            return value
    return ""


def _resolve_host_api_base_url() -> str:
    return str(os.getenv("COMPANION_HOST_BASE_URL", _DEFAULT_HOST_API_BASE_URL)).strip()


def _resolve_extension_id() -> str:
    return str(os.getenv("COMPANION_EXTENSION_ID", _DEFAULT_EXTENSION_ID)).strip() or _DEFAULT_EXTENSION_ID


def _resolve_host_api_key() -> str:
    return _read_first_nonempty_env(*_HOST_API_KEY_ENV_NAMES)


def _client() -> CompanionApiClient:
    base_url = _resolve_host_api_base_url()
    api_key = _resolve_host_api_key()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "code": "E_COMPANION_GATEWAY_API_KEY_REQUIRED",
                "message": "COMPANION_API_KEY or ORKET_API_KEY is required for Companion host API access.",
            },
        )
    timeout_seconds = float(os.getenv("COMPANION_TIMEOUT_SECONDS", "45"))
    return CompanionApiClient(
        base_url,
        timeout_seconds=timeout_seconds,
        api_key=api_key,
        extension_id=_resolve_extension_id(),
    )


def _raise_gateway_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        detail = str(exc or "").strip() or "Companion request failed."
        code = detail.split(":", 1)[0].strip()
        if not code.startswith("E_"):
            code = "E_COMPANION_REQUEST_INVALID"
        raise HTTPException(status_code=400, detail={"ok": False, "code": code, "message": detail}) from exc
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
async def status(request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().status()
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.get("/api/models")
async def models(request: Request, provider: str = "ollama") -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().models(provider=provider)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.get("/api/config")
async def get_config(session_id: str, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().get_config(session_id=session_id)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.patch("/api/config")
async def update_config(req: ConfigUpdateRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    _enforce_patch_size_limit(req.patch)
    try:
        return await _client().update_config(session_id=req.session_id, scope=req.scope, patch=req.patch)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.get("/api/history")
async def history(session_id: str, request: Request, limit: int = 50) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().history(session_id=session_id, limit=limit)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    _enforce_text_size_limit(
        value=req.message,
        max_bytes=_MAX_CHAT_MESSAGE_BYTES,
        code="E_COMPANION_CHAT_MESSAGE_TOO_LARGE",
        message=f"Chat message exceeds {_MAX_CHAT_MESSAGE_BYTES} bytes.",
    )
    try:
        return await _client().chat(
            session_id=req.session_id,
            message=req.message,
            provider=req.provider,
            model=req.model,
        )
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/session/clear-memory")
async def clear_memory(req: SessionRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().clear_session_memory(session_id=req.session_id)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.get("/api/voice/state")
async def voice_state(request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().voice_state()
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.get("/api/voice/voices")
async def voice_voices(request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().voice_voices()
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/control")
async def voice_control(req: VoiceControlRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    try:
        return await _client().voice_control(command=req.command, silence_delay_sec=req.silence_delay_sec)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/transcribe")
async def voice_transcribe(req: TranscribeRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    _enforce_text_size_limit(
        value=req.audio_b64,
        max_bytes=_MAX_AUDIO_B64_BYTES,
        code="E_COMPANION_AUDIO_PAYLOAD_TOO_LARGE",
        message=f"Audio payload exceeds {_MAX_AUDIO_B64_BYTES} bytes.",
    )
    try:
        return await _client().voice_transcribe(
            audio_b64=req.audio_b64,
            mime_type=req.mime_type,
            language_hint=req.language_hint,
        )
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/synthesize")
async def voice_synthesize(req: SynthesizeRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    _enforce_text_size_limit(
        value=req.text,
        max_bytes=_MAX_SYNTH_TEXT_BYTES,
        code="E_COMPANION_SYNTH_TEXT_TOO_LARGE",
        message=f"Synthesis text exceeds {_MAX_SYNTH_TEXT_BYTES} bytes.",
    )
    try:
        return await _client().voice_synthesize(
            text=req.text,
            voice_id=req.voice_id,
            emotion_hint=req.emotion_hint,
            speed=req.speed,
        )
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)


@app.post("/api/voice/cadence/suggest")
async def voice_cadence_suggest(req: CadenceSuggestRequest, request: Request) -> dict[str, Any]:
    _enforce_gateway_request_policy(request)
    _enforce_text_size_limit(
        value=req.text,
        max_bytes=_MAX_CADENCE_TEXT_BYTES,
        code="E_COMPANION_CADENCE_TEXT_TOO_LARGE",
        message=f"Cadence text exceeds {_MAX_CADENCE_TEXT_BYTES} bytes.",
    )
    try:
        return await _client().voice_cadence_suggest(session_id=req.session_id, text=req.text)
    except (httpx.HTTPError, ValueError) as exc:
        _raise_gateway_error(exc)
