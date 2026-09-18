from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.tts_piper import PiperTTSProvider
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from orket.services.extension_memory_namespace import (
    profile_key,
    query_extension_profile_records,
    unscoped_profile_key,
)
from orket.services.extension_memory_namespace import (
    scoped_session_id as _scoped_session_id,
)
from orket.services.scoped_memory_store import ScopedMemoryRecord, ScopedMemoryStore
from orket_extension_sdk.audio import AudioClip, TTSProvider, VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse


def validate_memory_scope(scope: str) -> str:
    normalized = str(scope or "").strip()
    if normalized not in {"session_memory", "profile_memory", "episodic_memory"}:
        raise ValueError(f"E_EXTENSION_RUNTIME_MEMORY_SCOPE_INVALID: {normalized or '<empty>'}")
    return normalized


def validate_clear_scope(scope: str) -> str:
    normalized = str(scope or "").strip()
    if normalized not in {"session_memory", "episodic_memory"}:
        raise ValueError(f"E_EXTENSION_RUNTIME_MEMORY_CLEAR_SCOPE_INVALID: {normalized or '<empty>'}")
    return normalized


def scoped_session_id(extension_id: str, session_id: str) -> str:
    return _scoped_session_id(extension_id, session_id, require_session_id=True)
def serialize_record(extension_id: str, record: ScopedMemoryRecord) -> dict[str, Any]:
    key = unscoped_profile_key(extension_id, record.key) if record.scope == "profile_memory" else str(record.key or "")
    session_id = ""
    if record.scope != "profile_memory":
        scoped_prefix = f"ext:{extension_id}:"
        session_id = str(record.session_id or "")
        if session_id.startswith(scoped_prefix):
            session_id = session_id[len(scoped_prefix) :]
    return {
        "scope": str(record.scope or ""),
        "key": key,
        "value": str(record.value or ""),
        "session_id": session_id,
        "metadata": dict(record.metadata),
        "created_at": str(record.created_at or ""),
        "updated_at": str(record.updated_at or ""),
    }


def serialize_voice_info(voice: VoiceInfo) -> dict[str, Any]:
    return {
        "voice_id": str(voice.voice_id),
        "display_name": str(voice.display_name),
        "language": str(voice.language),
        "tags": [str(tag) for tag in list(voice.tags or [])],
    }


async def query_profile_records(
    *,
    memory_store: ScopedMemoryStore,
    extension_id: str,
    query: str,
    limit: int,
) -> list[ScopedMemoryRecord]:
    normalized_query = str(query or "").strip()
    if normalized_query.startswith("key:"):
        requested_key = normalized_query.split(":", 1)[1].strip()
        if not requested_key:
            return []
        row = await memory_store.read_profile(key=profile_key(extension_id, requested_key))
        return [row] if row is not None else []

    return await query_extension_profile_records(
        memory_store=memory_store,
        extension_id=extension_id,
        query=normalized_query,
        limit=limit,
    )


async def generate_response(
    *,
    request: GenerateRequest,
    model_provider: LocalModelCapabilityProvider,
    provider_override: str,
    model_override: str,
) -> GenerateResponse:
    return await run_owned_thread(
        lambda: _generate_response_sync(request, model_provider, provider_override, model_override),
        label="extension model generation and client cleanup",
    )


async def synthesize_audio(
    provider: TTSProvider, text: str, voice_id: str, emotion_hint: str, speed: float,
) -> tuple[AudioClip, dict[str, Any] | None, str, dict[str, Any] | None]:
    # Embedding subclasses retain their authoritative synchronous SDK implementation.
    if type(provider) is PiperTTSProvider:
        result = await provider.synthesize_async(text, voice_id, emotion_hint, speed)
        lifetime = result.command.lifetime() if result.command is not None else None
        return result.clip, lifetime, result.voice.voice_id, result.voice.metadata()
    clip = await run_owned_thread(lambda: provider.synthesize(text, voice_id, emotion_hint, speed),
                                  label="extension speech synthesis")
    return clip, None, voice_id, None


def _generate_response_sync(request, model_provider, provider_override, model_override) -> GenerateResponse:
    provider = str(provider_override or "").strip()
    model = str(model_override or "").strip()
    if not provider and not model:
        return model_provider.generate(request)
    if not isinstance(model_provider, LocalModelCapabilityProvider):
        # Dependency-injected providers remain authoritative in tests and embeddings;
        # only the built-in local provider supports reconstructing override-specific clients here.
        return model_provider.generate(request)
    provider_client = LocalModelCapabilityProvider(
        model=model or DEFAULT_LOCAL_MODEL, temperature=float(request.temperature), seed=None, provider=provider,
    )
    try:
        return provider_client.generate(request)
    finally:
        provider_client.close()


def default_memory_db_path(project_root: Path) -> Path:
    return project_root / ".orket" / "durable" / "db" / "extension_runtime_memory.db"
