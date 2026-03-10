from __future__ import annotations

from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from orket.logging import log_event


class CompanionChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    provider: str = ""
    model: str = ""


class CompanionConfigUpdateRequest(BaseModel):
    session_id: str = Field(min_length=1)
    scope: Literal["profile", "session", "next_turn"] = "next_turn"
    patch: dict[str, Any] = Field(default_factory=dict)


class CompanionVoiceControlRequest(BaseModel):
    command: Literal["start", "stop", "submit"]
    silence_delay_sec: float | None = None


class CompanionTranscribeRequest(BaseModel):
    audio_b64: str = Field(min_length=1)
    mime_type: str = Field(default="audio/wav", min_length=1)
    language_hint: str = ""


class CompanionSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str = ""
    emotion_hint: str = "neutral"
    speed: float = 1.0


class CompanionCadenceSuggestRequest(BaseModel):
    session_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class CompanionSessionRequest(BaseModel):
    session_id: str = Field(min_length=1)


def build_companion_router(*, service_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/companion/status")
    async def companion_status():
        service = service_getter()
        return await service.status()

    @router.get("/companion/config")
    async def companion_get_config(session_id: str):
        service = service_getter()
        try:
            config = await service.get_config(session_id=session_id)
        except ValueError as exc:
            _raise_companion_http_error(exc)
        return {"ok": True, "session_id": session_id, "config": config.model_dump(mode="json", exclude_none=True)}

    @router.patch("/companion/config")
    async def companion_update_config(req: CompanionConfigUpdateRequest):
        service = service_getter()
        try:
            config = await service.update_config(
                session_id=req.session_id,
                scope=req.scope,
                patch=req.patch,
            )
        except ValueError as exc:
            _raise_companion_http_error(exc)
        return {"ok": True, "session_id": req.session_id, "scope": req.scope, "config": config.model_dump(mode="json")}

    @router.get("/companion/history")
    async def companion_history(session_id: str, limit: int = 50):
        service = service_getter()
        try:
            history = await service.get_history(session_id=session_id, limit=limit)
        except ValueError as exc:
            _raise_companion_http_error(exc)
        return {"ok": True, "session_id": session_id, "history": history}

    @router.get("/companion/models")
    async def companion_models(provider: str = "ollama"):
        service = service_getter()
        try:
            return await service.list_models(provider=provider)
        except ValueError as exc:
            _raise_companion_http_error(exc)
        except Exception as exc:
            requested = str(provider or "").strip().lower() or "ollama"
            log_event(
                "companion_model_catalog_unavailable",
                {"provider": requested, "error": str(exc)},
            )
            default_model = "Command-R:35B" if requested == "ollama" else ""
            fallback_models = [default_model] if default_model else []
            return {
                "ok": True,
                "requested_provider": requested,
                "canonical_provider": "openai_compat" if requested in {"lmstudio", "openai_compat"} else "ollama",
                "base_url": "",
                "models": fallback_models,
                "default_model": default_model,
                "degraded": True,
            }

    @router.post("/companion/chat")
    async def companion_chat(req: CompanionChatRequest):
        service = service_getter()
        try:
            return await service.chat(
                session_id=req.session_id,
                message=req.message,
                provider=req.provider,
                model=req.model,
            )
        except ValueError as exc:
            _raise_companion_http_error(exc)

    @router.get("/companion/voice/state")
    async def companion_voice_state():
        service = service_getter()
        return await service.voice_state()

    @router.get("/companion/voice/voices")
    async def companion_voice_voices():
        service = service_getter()
        return await service.tts_voices()

    @router.post("/companion/voice/control")
    async def companion_voice_control(req: CompanionVoiceControlRequest):
        service = service_getter()
        try:
            result = await service.voice_control(command=req.command, silence_delay_seconds=req.silence_delay_sec)
        except ValueError as exc:
            _raise_companion_http_error(exc)
        return {
            "ok": result.ok,
            "state": result.state,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    @router.post("/companion/voice/transcribe")
    async def companion_voice_transcribe(req: CompanionTranscribeRequest):
        service = service_getter()
        try:
            result = await service.transcribe(
                audio_b64=req.audio_b64,
                mime_type=req.mime_type,
                language_hint=req.language_hint,
            )
        except ValueError as exc:
            _raise_companion_http_error(exc)
        return {
            "ok": result.ok,
            "text": result.text,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    @router.post("/companion/voice/synthesize")
    async def companion_voice_synthesize(req: CompanionSynthesizeRequest):
        service = service_getter()
        try:
            return await service.synthesize(
                text=req.text,
                voice_id=req.voice_id,
                emotion_hint=req.emotion_hint,
                speed=req.speed,
            )
        except ValueError as exc:
            _raise_companion_http_error(exc)

    @router.post("/companion/voice/cadence/suggest")
    async def companion_voice_cadence_suggest(req: CompanionCadenceSuggestRequest):
        service = service_getter()
        try:
            return await service.suggest_voice_cadence(
                session_id=req.session_id,
                text=req.text,
            )
        except ValueError as exc:
            _raise_companion_http_error(exc)

    @router.post("/companion/session/clear-memory")
    async def companion_clear_session_memory(req: CompanionSessionRequest):
        service = service_getter()
        try:
            return await service.clear_session_memory(session_id=req.session_id)
        except ValueError as exc:
            _raise_companion_http_error(exc)

    return router


def _raise_companion_http_error(exc: ValueError) -> None:
    detail = str(exc or "").strip() or "Companion request failed."
    code = _resolve_error_code(detail)
    raise HTTPException(
        status_code=400,
        detail={"ok": False, "code": code, "message": detail},
    ) from exc


def _resolve_error_code(detail: str) -> str:
    prefix = detail.split(":", 1)[0].strip()
    if prefix.startswith("E_"):
        return prefix
    return "E_COMPANION_REQUEST_INVALID"

