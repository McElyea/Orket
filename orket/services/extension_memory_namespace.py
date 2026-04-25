from __future__ import annotations

import re
from collections.abc import Sequence

from orket.services.scoped_memory_store import ScopedMemoryRecord, ScopedMemoryStore

_EXTENSION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def validate_extension_id(extension_id: str) -> str:
    normalized = str(extension_id or "").strip()
    if not normalized:
        raise ValueError("E_EXTENSION_RUNTIME_EXTENSION_ID_REQUIRED")
    if not _EXTENSION_ID_RE.fullmatch(normalized):
        raise ValueError("E_EXTENSION_RUNTIME_EXTENSION_ID_INVALID")
    return normalized


def scoped_session_id(extension_id: str, session_id: str, *, require_session_id: bool) -> str:
    normalized_extension_id = validate_extension_id(extension_id)
    normalized_session_id = str(session_id or "").strip()
    if require_session_id and not normalized_session_id:
        raise ValueError("E_EXTENSION_RUNTIME_SESSION_ID_REQUIRED")
    resolved_session_id = normalized_session_id or "__default_session__"
    return f"ext:{normalized_extension_id}:{resolved_session_id}"


def profile_prefix(extension_id: str) -> str:
    return f"ext:{validate_extension_id(extension_id)}:"


def profile_key(extension_id: str, key: str) -> str:
    return f"{profile_prefix(extension_id)}{str(key or '').strip()}"


def unscoped_profile_key(extension_id: str, key: str) -> str:
    prefix = profile_prefix(extension_id)
    normalized_key = str(key or "")
    if normalized_key.startswith(prefix):
        return normalized_key[len(prefix) :]
    return normalized_key


async def query_extension_profile_records(
    *,
    memory_store: ScopedMemoryStore,
    extension_id: str,
    query: str,
    limit: int,
    list_limit: int = 2000,
) -> list[ScopedMemoryRecord]:
    normalized_query = str(query or "").strip()
    if normalized_query.startswith("key:"):
        requested_key = normalized_query.split(":", 1)[1].strip()
        if not requested_key:
            return []
        row = await memory_store.read_profile(key=profile_key(extension_id, requested_key))
        return [row] if row is not None else []

    rows = await memory_store.list_profile(limit=max(int(limit), int(list_limit)))
    return _filter_extension_profile_rows(rows=rows, extension_id=extension_id, query=normalized_query, limit=limit)


def _filter_extension_profile_rows(
    *,
    rows: Sequence[ScopedMemoryRecord],
    extension_id: str,
    query: str,
    limit: int,
) -> list[ScopedMemoryRecord]:
    prefix = profile_prefix(extension_id)
    needle = str(query or "").strip().lower()
    filtered: list[ScopedMemoryRecord] = []
    bounded_limit = max(1, int(limit))
    for row in rows:
        if not row.key.startswith(prefix):
            continue
        plain_key = unscoped_profile_key(extension_id, row.key)
        if needle and needle not in plain_key.lower() and needle not in str(row.value or "").lower():
            continue
        filtered.append(row)
        if len(filtered) >= bounded_limit:
            break
    return filtered


__all__ = [
    "profile_key",
    "profile_prefix",
    "query_extension_profile_records",
    "scoped_session_id",
    "unscoped_profile_key",
    "validate_extension_id",
]
