from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.capabilities.tts_piper import build_tts_provider
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.runtime.provider_runtime_target import list_provider_models
from orket.services.profile_write_policy import ProfileWritePolicy, ProfileWritePolicyError
from orket.services.scoped_memory_store import ScopedMemoryRecord, ScopedMemoryStore
from orket_extension_sdk.audio import TTSProvider, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest
from orket_extension_sdk.voice import (
    TranscribeRequest,
    VoiceTurnControlRequest,
)

from .extension_runtime_support import (
    default_memory_db_path,
    generate_response,
    profile_key,
    query_profile_records,
    scoped_session_id,
    serialize_record,
    serialize_voice_info,
    validate_clear_scope,
    validate_extension_id,
    validate_memory_scope,
)


@dataclass(slots=True)
class _ExtensionRuntimeState:
    voice_controller: HostVoiceTurnController
    active_sessions: set[str] = field(default_factory=set)


class ExtensionRuntimeService:
    def __init__(
        self,
        *,
        project_root: Path,
        model_provider: LocalModelCapabilityProvider | None = None,
        memory_store: ScopedMemoryStore | None = None,
        stt_provider: HostSTTCapabilityProvider | None = None,
        tts_provider: TTSProvider | None = None,
    ) -> None:
        self._project_root = project_root.resolve()
        self._model_provider = model_provider or LocalModelCapabilityProvider(
            model=DEFAULT_LOCAL_MODEL,
            temperature=0.2,
            seed=None,
        )
        self._memory_store = memory_store or ScopedMemoryStore(
            default_memory_db_path(self._project_root),
            profile_write_policy=ProfileWritePolicy(),
        )
        self._stt_provider = stt_provider or HostSTTCapabilityProvider()
        self._tts_provider = tts_provider or build_tts_provider(input_config={})
        self._state_lock = asyncio.Lock()
        self._states: dict[str, _ExtensionRuntimeState] = {}

    async def status(self, *, extension_id: str) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        state = await self._extension_state(validated_extension_id)
        stt_available = await self._stt_available()
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "model_available": bool(await asyncio.to_thread(self._model_provider.is_available)),
            "stt_available": stt_available,
            "tts_available": await self._tts_available(),
            "text_only_degraded": not stt_available,
            "voice_state": state.voice_controller.state(),
            "voice_silence_delay_sec": state.voice_controller.silence_delay_seconds(),
            "active_sessions": len(state.active_sessions),
        }

    async def list_models(self, *, extension_id: str, provider: str = "") -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        requested_provider = str(provider or "").strip().lower() or "ollama"
        payload = await list_provider_models(
            provider=requested_provider,
            base_url=None,
            timeout_s=8.0,
            api_key=None,
        )
        models = [str(model).strip() for model in list(payload.get("models", []) or []) if str(model).strip()]
        default_model = "Command-R:35B" if requested_provider == "ollama" else ""
        if default_model not in models and models:
            default_model = models[0]
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "requested_provider": str(payload.get("requested_provider") or requested_provider),
            "canonical_provider": str(payload.get("canonical_provider") or requested_provider),
            "base_url": str(payload.get("base_url") or ""),
            "models": models,
            "default_model": default_model,
        }

    async def llm_generate(
        self,
        *,
        extension_id: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        temperature: float,
        stop_sequences: list[str],
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        request = GenerateRequest(
            system_prompt=str(system_prompt or ""),
            user_message=str(user_message or "").strip(),
            max_tokens=max(1, int(max_tokens)),
            temperature=float(temperature),
            stop_sequences=[str(token) for token in list(stop_sequences or []) if str(token).strip()],
        )
        if not request.user_message:
            raise ValueError("E_EXTENSION_RUNTIME_MESSAGE_REQUIRED")
        result = await generate_response(
            request=request,
            model_provider=self._model_provider,
            provider_override=provider,
            model_override=model,
        )
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "text": str(result.text or ""),
            "model": str(result.model or ""),
            "latency_ms": int(result.latency_ms),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    async def memory_query(
        self,
        *,
        extension_id: str,
        scope: str,
        session_id: str = "",
        query: str = "",
        limit: int = 10,
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        normalized_scope = validate_memory_scope(scope)
        bounded_limit = max(1, min(200, int(limit)))
        rows: list[ScopedMemoryRecord]
        if normalized_scope == "profile_memory":
            rows = await query_profile_records(
                memory_store=self._memory_store,
                extension_id=validated_extension_id,
                query=str(query or ""),
                limit=bounded_limit,
            )
        else:
            resolved_session_id = scoped_session_id(validated_extension_id, session_id)
            await self._record_active_session(validated_extension_id, resolved_session_id)
            if normalized_scope == "session_memory":
                rows = await self._memory_store.query_session(
                    session_id=resolved_session_id,
                    query=str(query or ""),
                    limit=bounded_limit,
                )
            else:
                rows = await self._memory_store.query_episodic(
                    session_id=resolved_session_id,
                    query=str(query or ""),
                    limit=bounded_limit,
                )
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "scope": normalized_scope,
            "records": [serialize_record(validated_extension_id, row) for row in rows],
        }

    async def memory_write(
        self,
        *,
        extension_id: str,
        scope: str,
        key: str,
        value: str,
        session_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        normalized_scope = validate_memory_scope(scope)
        normalized_key = str(key or "").strip()
        if not normalized_key:
            raise ValueError("E_EXTENSION_RUNTIME_MEMORY_KEY_REQUIRED")
        payload_metadata = dict(metadata or {})

        if normalized_scope == "profile_memory":
            try:
                row = await self._memory_store.write_profile(
                    key=profile_key(validated_extension_id, normalized_key),
                    value=str(value or ""),
                    metadata=payload_metadata,
                )
            except ProfileWritePolicyError as exc:
                raise ValueError(f"{exc.code}: {exc.message}") from exc
        else:
            resolved_session_id = scoped_session_id(validated_extension_id, session_id)
            await self._record_active_session(validated_extension_id, resolved_session_id)
            if normalized_scope == "session_memory":
                row = await self._memory_store.write_session(
                    session_id=resolved_session_id,
                    key=normalized_key,
                    value=str(value or ""),
                    metadata=payload_metadata,
                )
            else:
                row = await self._memory_store.write_episodic(
                    session_id=resolved_session_id,
                    key=normalized_key,
                    value=str(value or ""),
                    metadata=payload_metadata,
                )

        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "scope": normalized_scope,
            "record": serialize_record(validated_extension_id, row),
        }

    async def memory_clear(
        self,
        *,
        extension_id: str,
        scope: str,
        session_id: str,
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        normalized_scope = validate_clear_scope(scope)
        resolved_session_id = scoped_session_id(validated_extension_id, session_id)
        state = await self._extension_state(validated_extension_id)
        if normalized_scope == "session_memory":
            deleted_records = await self._memory_store.clear_session(session_id=resolved_session_id)
        else:
            deleted_records = await self._memory_store.clear_episodic(session_id=resolved_session_id)
        state.active_sessions.discard(resolved_session_id)
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "scope": normalized_scope,
            "session_id": str(session_id or "").strip(),
            "deleted_records": int(deleted_records),
        }

    async def voice_state(self, *, extension_id: str) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        state = await self._extension_state(validated_extension_id)
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "state": state.voice_controller.state(),
            "silence_delay_sec": state.voice_controller.silence_delay_seconds(),
        }

    async def voice_control(
        self,
        *,
        extension_id: str,
        command: str,
        silence_delay_seconds: float | None = None,
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        state = await self._extension_state(validated_extension_id)
        request = VoiceTurnControlRequest(
            command=str(command).strip() or "stop",  # type: ignore[arg-type]
            silence_delay_seconds=silence_delay_seconds,
        )
        result = await asyncio.to_thread(state.voice_controller.control, request)
        return {
            "ok": result.ok,
            "extension_id": validated_extension_id,
            "state": result.state,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    async def transcribe(
        self,
        *,
        extension_id: str,
        audio_b64: str,
        mime_type: str,
        language_hint: str = "",
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        try:
            audio_bytes = base64.b64decode(str(audio_b64 or "").encode("utf-8"), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("E_EXTENSION_RUNTIME_AUDIO_B64_INVALID") from exc
        request = TranscribeRequest(audio_bytes=audio_bytes, mime_type=mime_type, language_hint=language_hint)
        result = await asyncio.to_thread(self._stt_provider.transcribe, request)
        return {
            "ok": result.ok,
            "extension_id": validated_extension_id,
            "text": result.text,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    async def tts_voices(self, *, extension_id: str) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        voices = await self._tts_voices()
        serialized = [serialize_voice_info(voice) for voice in voices]
        return {
            "ok": True,
            "extension_id": validated_extension_id,
            "tts_available": bool(serialized),
            "default_voice_id": str(serialized[0]["voice_id"] if serialized else ""),
            "voices": serialized,
        }

    async def synthesize(
        self,
        *,
        extension_id: str,
        text: str,
        voice_id: str = "",
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> dict[str, Any]:
        validated_extension_id = validate_extension_id(extension_id)
        normalized_text = str(text or "").strip()
        if not normalized_text:
            raise ValueError("E_EXTENSION_RUNTIME_TTS_TEXT_REQUIRED")
        voices = await self._tts_voices()
        resolved_voice_id = str(voice_id or "").strip() or str((voices[0].voice_id if voices else "null") or "null")
        clip = await asyncio.to_thread(
            self._tts_provider.synthesize,
            normalized_text,
            resolved_voice_id,
            str(emotion_hint or "neutral"),
            float(speed),
        )
        samples = bytes(clip.samples or b"")
        return {
            "ok": bool(samples),
            "extension_id": validated_extension_id,
            "voice_id": resolved_voice_id,
            "sample_rate": int(clip.sample_rate),
            "channels": int(clip.channels),
            "format": str(clip.format or "pcm_s16le"),
            "audio_b64": base64.b64encode(samples).decode("utf-8"),
            "error_code": None if samples else "tts_unavailable",
            "error_message": "" if samples else "No TTS backend configured.",
        }

    async def _extension_state(self, extension_id: str) -> _ExtensionRuntimeState:
        async with self._state_lock:
            existing = self._states.get(extension_id)
            if existing is not None:
                return existing
            created = _ExtensionRuntimeState(voice_controller=HostVoiceTurnController())
            self._states[extension_id] = created
            return created

    async def _record_active_session(self, extension_id: str, resolved_session_id: str) -> None:
        state = await self._extension_state(extension_id)
        state.active_sessions.add(resolved_session_id)

    async def _stt_available(self) -> bool:
        probe = await asyncio.to_thread(self._stt_provider.transcribe, TranscribeRequest(audio_bytes=b""))
        return bool(probe.ok or str(probe.error_code or "") != "stt_unavailable")

    async def _tts_available(self) -> bool:
        return bool(await self._tts_voices())

    async def _tts_voices(self) -> list[VoiceInfo]:
        return await asyncio.to_thread(self._tts_provider.list_voices)
