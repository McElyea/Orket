from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Literal

from orket.adapters.execution.owned_io import run_owned_io
from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.adapters.storage.scoped_memory_repository import ScopedMemoryRepository
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.memory_inputs import memory_timestamp
from orket.runtime.truthful_memory_policy import evaluate_memory_write_policy

from .profile_write_policy import ProfileWritePolicy, ProfileWritePolicyError

MemoryScope = Literal["session_memory", "profile_memory", "episodic_memory"]


@dataclass(frozen=True)
class ScopedMemoryRecord:
    scope: MemoryScope
    key: str
    value: str
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class MemoryControls:
    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True
    episodic_memory_enabled: bool = False

    def effective_session_enabled(self) -> bool:
        return bool(self.session_memory_enabled)

    def effective_profile_enabled(self) -> bool:
        return bool(self.profile_memory_enabled)

    def effective_episodic_enabled(self) -> bool:
        return bool(self.episodic_memory_enabled)


class ScopedMemoryStore:
    def __init__(
        self,
        db_path: Path,
        *,
        profile_write_policy: ProfileWritePolicy | None = None,
        runtime_inputs: RuntimeInputService | None = None,
    ) -> None:
        (captured_path,) = capture_file_roots([db_path])
        self._repository = ScopedMemoryRepository(captured_path)
        self._profile_write_policy = profile_write_policy or ProfileWritePolicy()
        self._runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs

    async def ensure_initialized(self) -> None:
        await run_owned_io(self._repository.initialize, label="scoped-memory initialization", preserve_failure=True)

    async def write_session(
        self, *, session_id: str, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> ScopedMemoryRecord:
        return await self._write_reference("session_memory", session_id, key, value, metadata)

    async def write_episodic(
        self, *, session_id: str, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> ScopedMemoryRecord:
        return await self._write_reference("episodic_memory", session_id, key, value, metadata)

    async def _write_reference(self, scope, session_id, key, value, metadata):
        key, value = str(key or "").strip(), str(value or "")
        decision = evaluate_memory_write_policy(scope=scope, key=key, value=value, metadata=deepcopy(metadata or {}))
        captured = dict(
            scope=scope,
            session_id=self.normalize_session_id(scope, session_id),
            key=key,
            value=value,
            metadata_json=json.dumps(decision.metadata, sort_keys=True, separators=(",", ":")),
            timestamp=memory_timestamp(self._runtime_inputs.utc_now()),
        )
        return await run_owned_io(
            partial(self._persist_record, captured), label="scoped-memory write", preserve_failure=True
        )

    async def write_profile(
        self, *, key: str, value: str, metadata: dict[str, Any] | None = None
    ) -> ScopedMemoryRecord:
        key, value, captured = str(key or "").strip(), str(value or ""), deepcopy(metadata or {})
        self._profile_write_policy.validate(key=key, metadata=captured)
        payload = json.dumps(captured, sort_keys=True, separators=(",", ":"))
        timestamp = memory_timestamp(self._runtime_inputs.utc_now())
        return await run_owned_io(
            partial(self._persist_profile, key, value, payload, timestamp),
            label="profile-memory transaction",
            preserve_failure=True,
        )

    async def _persist_profile(self, key, value, payload, timestamp):
        await self.ensure_initialized()
        identity = dict(scope="profile_memory", session_id=self.normalize_session_id("profile_memory", ""), key=key)
        async with self._repository.transaction() as connection:
            raw = await self._repository.read(connection, **identity)
            existing = _row_to_record(raw) if raw is not None else None
            decision = evaluate_memory_write_policy(
                scope="profile_memory",
                key=key,
                value=value,
                metadata=json.loads(payload),
                existing_value=existing.value if existing else "",
                existing_metadata=existing.metadata if existing else {},
            )
            if not decision.allow_write:
                raise ProfileWritePolicyError(
                    code=str(decision.error_code or "E_PROFILE_MEMORY_WRITE_REJECTED"),
                    message=decision.error_message or f"Profile memory key '{key}' was rejected by memory policy.",
                )
            row = await self._repository.publish(
                connection,
                **identity,
                value=value,
                timestamp=timestamp,
                metadata_json=json.dumps(decision.metadata, sort_keys=True, separators=(",", ":")),
            )
            record = _required_record(row, scope="profile_memory")
        return record

    async def _persist_record(self, captured):
        await self.ensure_initialized()
        async with self._repository.transaction() as connection:
            row = await self._repository.publish(connection, **captured)
            record = _required_record(row, scope=captured["scope"])
        return record

    async def clear_session(self, *, session_id: str) -> int:
        return await self._clear("session_memory", self.normalize_session_id("session_memory", session_id))

    async def clear_episodic(self, *, session_id: str) -> int:
        return await self._clear("episodic_memory", self.normalize_session_id("episodic_memory", session_id))

    async def _clear(self, scope, session_id):
        async def operation():
            await self.ensure_initialized()
            return await self._repository.clear(scope=scope, session_id=session_id)

        return await run_owned_io(operation, label="scoped-memory clear", preserve_failure=True)

    async def _query_records(self, *, sql: str, args: tuple[Any, ...]) -> list[ScopedMemoryRecord]:
        rows = await run_owned_io(
            partial(self._repository.query, sql=sql, args=args), label="scoped-memory query", preserve_failure=True
        )
        return [_row_to_record(row) for row in rows]

    @staticmethod
    def normalize_session_id(scope: MemoryScope, session_id: str) -> str:
        if scope == "profile_memory":
            return "__profile__"
        normalized = str(session_id or "").strip()
        return normalized or "__default_session__"

    async def query_session(self, *, session_id: str, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("session_memory", session_id)
        bounded_limit = _bounded_limit(limit)
        normalized_query = str(query or "").strip()
        args: tuple[Any, ...]
        if normalized_query:
            like_query = f"%{normalized_query}%"
            sql = """
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'session_memory' AND session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, like_query, like_query, bounded_limit)
        else:
            sql = """
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'session_memory' AND session_id = ?
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, bounded_limit)
        return await self._query_records(sql=sql, args=args)

    async def query_episodic(self, *, session_id: str, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        resolved_session = self.normalize_session_id("episodic_memory", session_id)
        bounded_limit = _bounded_limit(limit)
        normalized_query = str(query or "").strip()
        args: tuple[Any, ...]
        if normalized_query:
            like_query = f"%{normalized_query}%"
            sql = """
                SELECT 'episodic_memory', session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_episodic_memory
                WHERE session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, like_query, like_query, bounded_limit)
        else:
            sql = """
                SELECT 'episodic_memory', session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_episodic_memory
                WHERE session_id = ?
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """
            args = (resolved_session, bounded_limit)
        return await self._query_records(sql=sql, args=args)

    async def read_profile(self, *, key: str) -> ScopedMemoryRecord | None:
        await self.ensure_initialized()
        rows = await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ? AND memory_key = ?
                LIMIT 1
                """,
            args=(self.normalize_session_id("profile_memory", ""), str(key or "").strip()),
        )
        return rows[0] if rows else None

    async def list_profile(self, *, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        return await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ?
                ORDER BY memory_key ASC, created_at ASC
                LIMIT ?
                """,
            args=(self.normalize_session_id("profile_memory", ""), _bounded_limit(limit)),
        )

    async def query_profile(self, *, query: str, limit: int) -> list[ScopedMemoryRecord]:
        await self.ensure_initialized()
        normalized_query = str(query or "").strip()
        like_query = f"%{normalized_query}%"
        return await self._query_records(
            sql="""
                SELECT scope, session_id, memory_key, memory_value, metadata_json, created_at, updated_at
                FROM extension_memory
                WHERE scope = 'profile_memory' AND session_id = ? AND (memory_key LIKE ? OR memory_value LIKE ?)
                ORDER BY updated_at DESC, memory_key ASC
                LIMIT ?
                """,
            args=(self.normalize_session_id("profile_memory", ""), like_query, like_query, _bounded_limit(limit)),
        )


def _bounded_limit(limit: int) -> int:
    return max(1, min(200, int(limit)))


def _row_to_record(row: tuple[Any, ...]) -> ScopedMemoryRecord:
    scope_raw, session_id, key, value, metadata_json, created_at, updated_at = row
    scope = str(scope_raw or "").strip()
    metadata = _parse_metadata(metadata_json)
    return ScopedMemoryRecord(
        scope=scope,  # type: ignore[arg-type]
        key=str(key or ""),
        value=str(value or ""),
        session_id=str(session_id or "") if scope in {"session_memory", "episodic_memory"} else "",
        metadata=metadata,
        created_at=str(created_at or ""),
        updated_at=str(updated_at or ""),
    )


def _parse_metadata(payload: Any) -> dict[str, Any]:
    raw = str(payload or "")
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return {str(key): value for key, value in decoded.items()}
    return {}


def _required_record(row, *, scope):
    if row is None:
        code = (
            "E_SCOPED_MEMORY_EPISODIC_WRITE_READBACK_FAILED"
            if scope == "episodic_memory"
            else "E_SCOPED_MEMORY_WRITE_READBACK_FAILED"
        )
        raise RuntimeError(code)
    return _row_to_record(row)
