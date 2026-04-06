from __future__ import annotations

from pathlib import Path

from orket.capabilities.sync_bridge import run_coro_sync
from orket.services.profile_write_policy import ProfileWritePolicy, ProfileWritePolicyError
from orket.services.scoped_memory_store import MemoryControls, ScopedMemoryRecord, ScopedMemoryStore
from orket_extension_sdk.memory import (
    MemoryScope as SDKMemoryScope,
    MemoryProvider,
    MemoryQueryRequest,
    MemoryQueryResponse,
    MemoryRecord,
    MemoryWriteRequest,
    MemoryWriteResponse,
)


class SQLiteMemoryCapabilityProvider(MemoryProvider):
    def __init__(
        self,
        db_path: Path,
        *,
        controls: MemoryControls | None = None,
        profile_write_policy: ProfileWritePolicy | None = None,
    ) -> None:
        self._store = ScopedMemoryStore(db_path.resolve(), profile_write_policy=profile_write_policy)
        self._controls = controls or MemoryControls()

    async def _write_async(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        if request.scope == "session_memory":
            if not self._controls.effective_session_enabled():
                return self._disabled_write_response(request=request, error_code="memory_session_disabled")
            record = await self._store.write_session(
                session_id=request.session_id,
                key=request.key,
                value=request.value,
                metadata=request.metadata,
            )
            return MemoryWriteResponse(
                ok=True,
                scope=request.scope,
                key=record.key,
                session_id=record.session_id,
            )

        if not self._controls.effective_profile_enabled():
            return self._disabled_write_response(request=request, error_code="memory_profile_disabled")
        try:
            record = await self._store.write_profile(
                key=request.key,
                value=request.value,
                metadata=request.metadata,
            )
        except ProfileWritePolicyError as exc:
            return MemoryWriteResponse(
                ok=False,
                scope=request.scope,
                key=request.key,
                error_code=exc.code,
                error_message=exc.message,
            )
        return MemoryWriteResponse(
            ok=True,
            scope=request.scope,
            key=record.key,
            session_id="",
        )

    async def _query_async(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        records: list[ScopedMemoryRecord]
        if request.scope == "session_memory":
            if not self._controls.effective_session_enabled():
                return self._disabled_query_response(error_code="memory_session_disabled")
            records = await self._store.query_session(
                session_id=request.session_id,
                query=request.query,
                limit=request.limit,
            )
        else:
            if not self._controls.effective_profile_enabled():
                return self._disabled_query_response(error_code="memory_profile_disabled")
            query = str(request.query or "").strip()
            if query.startswith("key:"):
                key = query.split(":", 1)[1].strip()
                row = await self._store.read_profile(key=key)
                records = [row] if row is not None else []
            elif query:
                records = await self._store.query_profile(query=query, limit=request.limit)
            else:
                records = await self._store.list_profile(limit=request.limit)
        sdk_records = [self._to_sdk_record(record) for record in records]
        return MemoryQueryResponse(ok=True, records=sdk_records)

    def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        return run_coro_sync(self._write_async(request))

    def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        return run_coro_sync(self._query_async(request))

    def clear_session(self, session_id: str) -> int:
        return run_coro_sync(self._store.clear_session(session_id=session_id))

    @staticmethod
    def _to_sdk_record(record: ScopedMemoryRecord) -> MemoryRecord:
        scope = record.scope
        if scope not in {"session_memory", "profile_memory"}:
            raise ValueError(f"Unsupported SDK memory scope: {scope}")
        sdk_scope: SDKMemoryScope = "session_memory" if scope == "session_memory" else "profile_memory"
        return MemoryRecord(
            scope=sdk_scope,
            key=record.key,
            value=record.value,
            session_id=record.session_id if sdk_scope == "session_memory" else "",
            metadata=dict(record.metadata),
        )

    @staticmethod
    def _disabled_write_response(*, request: MemoryWriteRequest, error_code: str) -> MemoryWriteResponse:
        return MemoryWriteResponse(
            ok=False,
            scope=request.scope,
            key=request.key,
            session_id=request.session_id if request.scope == "session_memory" else "",
            error_code=error_code,
            error_message="Memory writes are disabled by runtime controls.",
        )

    @staticmethod
    def _disabled_query_response(*, error_code: str) -> MemoryQueryResponse:
        return MemoryQueryResponse(
            ok=False,
            records=[],
            error_code=error_code,
            error_message="Memory reads are disabled by runtime controls.",
        )
