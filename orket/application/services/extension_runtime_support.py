from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.services.scoped_memory_store import ScopedMemoryRecord, ScopedMemoryStore
from orket_extension_sdk.audio import VoiceInfo
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def validate_extension_id(extension_id: str) -> str:
    normalized = str(extension_id or "").strip()
    if not normalized:
        raise ValueError("E_EXTENSION_RUNTIME_EXTENSION_ID_REQUIRED")
    if not _EXTENSION_ID_RE.fullmatch(normalized):
        raise ValueError("E_EXTENSION_RUNTIME_EXTENSION_ID_INVALID")
    return normalized


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
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        raise ValueError("E_EXTENSION_RUNTIME_SESSION_ID_REQUIRED")
    return f"ext:{extension_id}:{normalized_session_id}"


def profile_prefix(extension_id: str) -> str:
    return f"ext:{extension_id}:"


def profile_key(extension_id: str, key: str) -> str:
    return f"{profile_prefix(extension_id)}{str(key or '').strip()}"


def unscoped_profile_key(extension_id: str, key: str) -> str:
    prefix = profile_prefix(extension_id)
    if key.startswith(prefix):
        return key[len(prefix) :]
    return key


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

    rows = await memory_store.list_profile(limit=2000)
    prefix = profile_prefix(extension_id)
    filtered: list[ScopedMemoryRecord] = []
    needle = normalized_query.lower()
    for row in rows:
        if not row.key.startswith(prefix):
            continue
        plain_key = unscoped_profile_key(extension_id, row.key)
        if needle and needle not in plain_key.lower() and needle not in str(row.value or "").lower():
            continue
        filtered.append(row)
        if len(filtered) >= limit:
            break
    return filtered


async def generate_response(
    *,
    request: GenerateRequest,
    model_provider: LocalModelCapabilityProvider,
    provider_override: str,
    model_override: str,
) -> GenerateResponse:
    provider = str(provider_override or "").strip()
    model = str(model_override or "").strip()
    if not provider and not model:
        return await asyncio.to_thread(model_provider.generate, request)
    if not isinstance(model_provider, LocalModelCapabilityProvider):
        # Dependency-injected providers remain authoritative in tests and embeddings;
        # only the built-in local provider supports reconstructing override-specific clients here.
        return await asyncio.to_thread(model_provider.generate, request)

    previous_llm_provider = os.environ.get("ORKET_LLM_PROVIDER")
    previous_model_provider = os.environ.get("ORKET_MODEL_PROVIDER")
    try:
        if provider:
            os.environ["ORKET_LLM_PROVIDER"] = provider
            os.environ["ORKET_MODEL_PROVIDER"] = provider
        provider_client = LocalModelCapabilityProvider(
            model=model or DEFAULT_LOCAL_MODEL,
            temperature=float(request.temperature),
            seed=None,
        )
        return await asyncio.to_thread(provider_client.generate, request)
    finally:
        _restore_env("ORKET_LLM_PROVIDER", previous_llm_provider)
        _restore_env("ORKET_MODEL_PROVIDER", previous_model_provider)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def default_memory_db_path(project_root: Path) -> Path:
    return project_root / ".orket" / "durable" / "db" / "extension_runtime_memory.db"
