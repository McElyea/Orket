from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from orket.logging import log_event


class ExtensionRuntimeGenerateRequest(BaseModel):
    system_prompt: str = ""
    user_message: str = Field(min_length=1)
    max_tokens: int = Field(default=256, ge=1, le=8192)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    stop_sequences: list[str] = Field(default_factory=list)
    provider: str = ""
    model: str = ""


class ExtensionRuntimeMemoryQueryRequest(BaseModel):
    scope: Literal["session_memory", "profile_memory", "episodic_memory"]
    query: str = ""
    limit: int = Field(default=10, ge=1, le=200)
    session_id: str = ""


class ExtensionRuntimeMemoryWriteRequest(BaseModel):
    scope: Literal["session_memory", "profile_memory", "episodic_memory"]
    key: str = Field(min_length=1)
    value: str = ""
    session_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtensionRuntimeMemoryClearRequest(BaseModel):
    scope: Literal["session_memory", "episodic_memory"]
    session_id: str = Field(min_length=1)


class ExtensionRuntimeVoiceControlRequest(BaseModel):
    command: Literal["start", "stop", "submit"]
    silence_delay_sec: float | None = None


class ExtensionRuntimeTranscribeRequest(BaseModel):
    audio_b64: str = Field(min_length=1)
    mime_type: str = Field(default="audio/wav", min_length=1)
    language_hint: str = ""


class ExtensionRuntimeSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1)
    voice_id: str = ""
    emotion_hint: str = "neutral"
    speed: float = 1.0


def build_extension_runtime_router(*, service_getter: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/extensions/{extension_id}/runtime/status")
    async def extension_runtime_status(extension_id: str):
        service = service_getter()
        try:
            return await service.status(extension_id=extension_id)
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.get("/extensions/{extension_id}/runtime/models")
    async def extension_runtime_models(extension_id: str, provider: str = "ollama"):
        service = service_getter()
        try:
            return await service.list_models(extension_id=extension_id, provider=provider)
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)
        except Exception as exc:
            requested = str(provider or "").strip().lower() or "ollama"
            log_event(
                "extension_runtime_model_catalog_unavailable",
                {"extension_id": extension_id, "provider": requested, "error": str(exc)},
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "ok": False,
                    "code": "E_EXTENSION_RUNTIME_MODEL_CATALOG_UNAVAILABLE",
                    "message": (
                        f"Extension runtime model catalog unavailable for provider '{requested}' "
                        f"and extension '{extension_id}'."
                    ),
                    "requested_provider": requested,
                    "extension_id": extension_id,
                    "degraded": True,
                },
            ) from exc

    @router.post("/extensions/{extension_id}/runtime/llm/generate")
    async def extension_runtime_generate(extension_id: str, req: ExtensionRuntimeGenerateRequest):
        service = service_getter()
        try:
            return await service.llm_generate(
                extension_id=extension_id,
                system_prompt=req.system_prompt,
                user_message=req.user_message,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                stop_sequences=req.stop_sequences,
                provider=req.provider,
                model=req.model,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/memory/query")
    async def extension_runtime_memory_query(extension_id: str, req: ExtensionRuntimeMemoryQueryRequest):
        service = service_getter()
        try:
            return await service.memory_query(
                extension_id=extension_id,
                scope=req.scope,
                session_id=req.session_id,
                query=req.query,
                limit=req.limit,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/memory/write")
    async def extension_runtime_memory_write(extension_id: str, req: ExtensionRuntimeMemoryWriteRequest):
        service = service_getter()
        try:
            return await service.memory_write(
                extension_id=extension_id,
                scope=req.scope,
                key=req.key,
                value=req.value,
                session_id=req.session_id,
                metadata=req.metadata,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/memory/clear")
    async def extension_runtime_memory_clear(extension_id: str, req: ExtensionRuntimeMemoryClearRequest):
        service = service_getter()
        try:
            return await service.memory_clear(
                extension_id=extension_id,
                scope=req.scope,
                session_id=req.session_id,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.get("/extensions/{extension_id}/runtime/voice/state")
    async def extension_runtime_voice_state(extension_id: str):
        service = service_getter()
        try:
            return await service.voice_state(extension_id=extension_id)
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/voice/control")
    async def extension_runtime_voice_control(extension_id: str, req: ExtensionRuntimeVoiceControlRequest):
        service = service_getter()
        try:
            return await service.voice_control(
                extension_id=extension_id,
                command=req.command,
                silence_delay_seconds=req.silence_delay_sec,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/voice/transcribe")
    async def extension_runtime_voice_transcribe(extension_id: str, req: ExtensionRuntimeTranscribeRequest):
        service = service_getter()
        try:
            return await service.transcribe(
                extension_id=extension_id,
                audio_b64=req.audio_b64,
                mime_type=req.mime_type,
                language_hint=req.language_hint,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.get("/extensions/{extension_id}/runtime/tts/voices")
    async def extension_runtime_tts_voices(extension_id: str):
        service = service_getter()
        try:
            return await service.tts_voices(extension_id=extension_id)
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    @router.post("/extensions/{extension_id}/runtime/tts/synthesize")
    async def extension_runtime_tts_synthesize(extension_id: str, req: ExtensionRuntimeSynthesizeRequest):
        service = service_getter()
        try:
            return await service.synthesize(
                extension_id=extension_id,
                text=req.text,
                voice_id=req.voice_id,
                emotion_hint=req.emotion_hint,
                speed=req.speed,
            )
        except ValueError as exc:
            _raise_extension_runtime_http_error(exc)

    return router


def _raise_extension_runtime_http_error(exc: ValueError) -> None:
    detail = str(exc or "").strip() or "Extension runtime request failed."
    code = _resolve_error_code(detail)
    raise HTTPException(
        status_code=400,
        detail={"ok": False, "code": code, "message": detail},
    ) from exc


def _resolve_error_code(detail: str) -> str:
    prefix = detail.split(":", 1)[0].strip()
    if prefix.startswith("E_"):
        return prefix
    return "E_EXTENSION_RUNTIME_REQUEST_INVALID"
