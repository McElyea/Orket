from __future__ import annotations

import asyncio
import base64
import binascii
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket.services.profile_write_policy import ProfileWritePolicy
from orket.services.scoped_memory_store import ScopedMemoryRecord, ScopedMemoryStore
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse
from orket_extension_sdk.voice import TranscribeRequest, TranscribeResponse, VoiceTurnControlRequest, VoiceTurnControlResponse

from .companion_config_models import CompanionConfig
from .config_precedence_resolver import ConfigPrecedenceResolver

CompanionConfigScope = Literal["profile", "session", "next_turn"]


@dataclass(slots=True)
class _SessionState:
    resolver: ConfigPrecedenceResolver
    history: list[dict[str, Any]] = field(default_factory=list)
    turn_index: int = 0


class CompanionRuntimeService:
    PROFILE_CONFIG_KEY = "companion_setting.config_json"
    _MAX_HISTORY = 100

    def __init__(
        self,
        *,
        project_root: Path,
        model_provider: LocalModelCapabilityProvider | None = None,
        memory_store: ScopedMemoryStore | None = None,
        voice_controller: HostVoiceTurnController | None = None,
        stt_provider: HostSTTCapabilityProvider | None = None,
    ) -> None:
        self._project_root = project_root.resolve()
        self._extension_defaults = _default_companion_config()
        self._model_provider = model_provider or LocalModelCapabilityProvider(
            model="qwen2.5-coder:7b",
            temperature=0.2,
            seed=None,
        )
        self._memory_store = memory_store or ScopedMemoryStore(
            self._project_root / ".orket" / "durable" / "db" / "companion_memory.db",
            profile_write_policy=ProfileWritePolicy(),
        )
        self._voice_controller = voice_controller or HostVoiceTurnController()
        self._stt_provider = stt_provider or HostSTTCapabilityProvider()
        self._state_lock = asyncio.Lock()
        self._initialized = False
        self._profile_defaults_cache: dict[str, Any] = {}
        self._sessions: dict[str, _SessionState] = {}

    async def ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._state_lock:
            if self._initialized:
                return
            self._profile_defaults_cache = await self._load_profile_defaults()
            self._initialized = True

    async def status(self) -> dict[str, Any]:
        await self.ensure_initialized()
        stt_available = await self._stt_available()
        return {
            "ok": True,
            "model_available": bool(await asyncio.to_thread(self._model_provider.is_available)),
            "stt_available": stt_available,
            "text_only_degraded": not stt_available,
            "voice_state": self._voice_controller.state(),
            "voice_silence_delay_sec": self._voice_controller.silence_delay_seconds(),
            "active_sessions": len(self._sessions),
        }

    async def get_config(self, *, session_id: str) -> CompanionConfig:
        session = await self._session_state(session_id)
        return session.resolver.preview(include_pending_next_turn=True)

    async def update_config(self, *, session_id: str, scope: CompanionConfigScope, patch: dict[str, Any]) -> CompanionConfig:
        await self.ensure_initialized()
        normalized_patch = _normalize_config_patch(patch)
        session = await self._session_state(session_id)
        current_payload = session.resolver.preview(include_pending_next_turn=True).model_dump(mode="json", exclude_none=True)
        candidate_payload = _merge_nested(current_payload, normalized_patch)
        CompanionConfig.model_validate(candidate_payload)

        if scope == "session":
            for section, value in normalized_patch.items():
                session.resolver.set_session_override(section, value)
            return session.resolver.preview(include_pending_next_turn=True)

        if scope == "next_turn":
            for section, value in normalized_patch.items():
                session.resolver.set_pending_next_turn(section, value)
            return session.resolver.preview(include_pending_next_turn=True)

        if scope != "profile":
            raise ValueError(f"E_COMPANION_CONFIG_SCOPE_INVALID: {scope}")

        async with self._state_lock:
            merged_profile = _merge_nested(self._profile_defaults_cache, normalized_patch)
            merged_config = _merge_nested(self._extension_defaults, merged_profile)
            CompanionConfig.model_validate(merged_config)
            self._profile_defaults_cache = merged_profile
            for state in self._sessions.values():
                state.resolver.set_profile_defaults(self._profile_defaults_cache)
        await self._persist_profile_defaults(self._profile_defaults_cache)
        return session.resolver.preview(include_pending_next_turn=True)

    async def get_history(self, *, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        session = await self._session_state(session_id)
        bounded_limit = max(1, min(200, int(limit)))
        return list(session.history[-bounded_limit:])

    async def chat(
        self,
        *,
        session_id: str,
        message: str,
        provider: str = "",
        model: str = "",
    ) -> dict[str, Any]:
        user_message = str(message or "").strip()
        if not user_message:
            raise ValueError("E_COMPANION_MESSAGE_REQUIRED")
        session = await self._session_state(session_id)
        config = session.resolver.resolve()
        memory_context = await self._build_memory_context(session_id=session_id, config=config)
        history_context = _format_history_context(session.history[-6:])
        system_prompt = _build_system_prompt(config=config, memory_context=memory_context, history_context=history_context)

        request = GenerateRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=256,
            temperature=0.2,
        )
        try:
            model_result = await self._generate_response(
                request=request,
                provider_override=provider,
                model_override=model,
            )
        except (RuntimeError, OSError, ValueError) as exc:
            raise ValueError(f"E_COMPANION_MODEL_GENERATION_FAILED: {exc}") from exc
        assistant_text = str(model_result.text or "").strip() or "I could not generate a response."
        session.turn_index += 1
        turn_id = f"turn.{session.turn_index:06d}"
        timestamp_utc = _utc_now_iso()
        session.history.append({"role": "user", "content": user_message, "timestamp_utc": timestamp_utc})
        session.history.append({"role": "assistant", "content": assistant_text, "timestamp_utc": timestamp_utc})
        if len(session.history) > self._MAX_HISTORY:
            session.history = session.history[-self._MAX_HISTORY :]

        if config.memory.session_memory_enabled:
            await self._memory_store.write_session(
                session_id=session_id,
                key=f"{turn_id}.user",
                value=user_message,
                metadata={"kind": "chat_input"},
            )
            await self._memory_store.write_session(
                session_id=session_id,
                key=f"{turn_id}.assistant",
                value=assistant_text,
                metadata={"kind": "chat_output"},
            )

        return {
            "ok": True,
            "session_id": session_id,
            "turn_id": turn_id,
            "message": assistant_text,
            "model": model_result.model,
            "latency_ms": model_result.latency_ms,
            "config": config.model_dump(mode="json", exclude_none=True),
            "text_only_degraded": not await self._stt_available(),
        }

    async def clear_session_memory(self, *, session_id: str) -> dict[str, Any]:
        session = await self._session_state(session_id)
        deleted = await self._memory_store.clear_session(session_id=session_id)
        session.history = []
        session.turn_index = 0
        session.resolver.clear_session()
        return {"ok": True, "session_id": session_id, "deleted_records": deleted}

    async def voice_state(self) -> dict[str, Any]:
        await self.ensure_initialized()
        return {
            "ok": True,
            "state": self._voice_controller.state(),
            "silence_delay_sec": self._voice_controller.silence_delay_seconds(),
        }

    async def voice_control(self, *, command: str, silence_delay_seconds: float | None = None) -> VoiceTurnControlResponse:
        await self.ensure_initialized()
        request = VoiceTurnControlRequest(
            command=str(command).strip() or "stop",  # type: ignore[arg-type]
            silence_delay_seconds=silence_delay_seconds,
        )
        return await asyncio.to_thread(self._voice_controller.control, request)

    async def transcribe(self, *, audio_b64: str, mime_type: str, language_hint: str = "") -> TranscribeResponse:
        await self.ensure_initialized()
        try:
            audio_bytes = base64.b64decode(str(audio_b64 or "").encode("utf-8"), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("E_COMPANION_AUDIO_B64_INVALID") from exc
        request = TranscribeRequest(audio_bytes=audio_bytes, mime_type=mime_type, language_hint=language_hint)
        return await asyncio.to_thread(self._stt_provider.transcribe, request)

    async def _session_state(self, session_id: str) -> _SessionState:
        await self.ensure_initialized()
        key = str(session_id or "").strip()
        if not key:
            raise ValueError("E_COMPANION_SESSION_ID_REQUIRED")
        async with self._state_lock:
            existing = self._sessions.get(key)
            if existing is not None:
                return existing
            resolver = ConfigPrecedenceResolver(
                extension_defaults=self._extension_defaults,
                profile_defaults=self._profile_defaults_cache,
            )
            created = _SessionState(resolver=resolver)
            self._sessions[key] = created
            return created

    async def _load_profile_defaults(self) -> dict[str, Any]:
        row = await self._memory_store.read_profile(key=self.PROFILE_CONFIG_KEY)
        if row is None:
            return {}
        raw = str(row.value or "").strip()
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
        return {}

    async def _persist_profile_defaults(self, payload: dict[str, Any]) -> None:
        await self._memory_store.write_profile(
            key=self.PROFILE_CONFIG_KEY,
            value=json.dumps(payload, sort_keys=True, separators=(",", ":")),
            metadata={"kind": "companion_config_profile_defaults"},
        )

    async def _build_memory_context(self, *, session_id: str, config: CompanionConfig) -> str:
        snippets: list[str] = []
        if config.memory.session_memory_enabled:
            rows = await self._memory_store.query_session(session_id=session_id, query="", limit=8)
            snippets.extend(_format_memory_rows(rows, prefix="session"))
        if config.memory.profile_memory_enabled:
            rows = await self._memory_store.list_profile(limit=8)
            snippets.extend(_format_memory_rows(rows, prefix="profile"))
        return "\n".join(snippets)

    async def _generate_response(
        self,
        *,
        request: GenerateRequest,
        provider_override: str,
        model_override: str,
    ) -> GenerateResponse:
        normalized_provider = str(provider_override or "").strip()
        normalized_model = str(model_override or "").strip()
        if not normalized_provider and not normalized_model:
            return await asyncio.to_thread(self._model_provider.generate, request)
        return await asyncio.to_thread(
            _generate_with_provider_overrides,
            request,
            normalized_provider,
            normalized_model,
        )

    async def _stt_available(self) -> bool:
        try:
            probe = await asyncio.to_thread(self._stt_provider.transcribe, TranscribeRequest(audio_bytes=b""))
        except (RuntimeError, OSError, ValueError):
            return False
        return bool(probe.ok)


def _default_companion_config() -> dict[str, Any]:
    config = CompanionConfig()
    return config.model_dump(mode="json", exclude_none=True)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_config_patch(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("E_COMPANION_CONFIG_PATCH_INVALID")
    normalized: dict[str, Any] = {}
    for section, value in payload.items():
        section_name = str(section or "").strip()
        if section_name not in {"mode", "memory", "voice"}:
            raise ValueError(f"E_COMPANION_CONFIG_SECTION_INVALID: {section_name}")
        if not isinstance(value, dict):
            raise ValueError(f"E_COMPANION_CONFIG_SECTION_PAYLOAD_INVALID: {section_name}")
        normalized[section_name] = value
    if not normalized:
        raise ValueError("E_COMPANION_CONFIG_PATCH_EMPTY")
    return normalized


def _merge_nested(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(base))
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested(merged[key], value)
        else:
            merged[key] = value
    return merged


def _build_system_prompt(*, config: CompanionConfig, memory_context: str, history_context: str) -> str:
    mode = config.mode
    sections = [
        "You are Companion running on Orket host runtime authority.",
        f"Role: {mode.role_id.value}",
        f"Relationship style: {mode.relationship_style.value}",
    ]
    if mode.custom_style:
        sections.append("Custom style settings:\n" + json.dumps(mode.custom_style, sort_keys=True))
    if memory_context.strip():
        sections.append("Retrieved memory context:\n" + memory_context)
    if history_context.strip():
        sections.append("Recent conversation context:\n" + history_context)
    return "\n\n".join(sections)


def _format_memory_rows(rows: list[ScopedMemoryRecord], *, prefix: str) -> list[str]:
    formatted: list[str] = []
    for row in rows:
        key = str(row.key or "").strip()
        value = str(row.value or "").strip()
        if not key and not value:
            continue
        formatted.append(f"- [{prefix}] {key}: {value}")
    return formatted


def _format_history_context(history_rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in history_rows:
        role = str(row.get("role") or "").strip()
        content = str(row.get("content") or "").strip()
        if role and content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def _generate_with_provider_overrides(
    request: GenerateRequest,
    provider_override: str,
    model_override: str,
) -> GenerateResponse:
    model = model_override or "qwen2.5-coder:7b"
    provider = provider_override.strip()
    previous_llm_provider = os.environ.get("ORKET_LLM_PROVIDER")
    previous_model_provider = os.environ.get("ORKET_MODEL_PROVIDER")
    try:
        if provider:
            os.environ["ORKET_LLM_PROVIDER"] = provider
            os.environ["ORKET_MODEL_PROVIDER"] = provider
        provider_client = LocalModelCapabilityProvider(
            model=model,
            temperature=0.2,
            seed=None,
        )
        return provider_client.generate(request)
    finally:
        if previous_llm_provider is None:
            os.environ.pop("ORKET_LLM_PROVIDER", None)
        else:
            os.environ["ORKET_LLM_PROVIDER"] = previous_llm_provider
        if previous_model_provider is None:
            os.environ.pop("ORKET_MODEL_PROVIDER", None)
        else:
            os.environ["ORKET_MODEL_PROVIDER"] = previous_model_provider
