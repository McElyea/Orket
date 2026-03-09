from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

MemoryScope = Literal["session_memory", "profile_memory"]


@dataclass(frozen=True)
class MemoryWriteRequest:
    scope: MemoryScope
    key: str
    value: str
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryWriteResponse:
    ok: bool
    scope: MemoryScope
    key: str
    session_id: str = ""
    error_code: str | None = None
    error_message: str = ""


@dataclass(frozen=True)
class MemoryQueryRequest:
    scope: MemoryScope
    query: str = ""
    limit: int = 10
    session_id: str = ""


@dataclass(frozen=True)
class MemoryRecord:
    scope: MemoryScope
    key: str
    value: str
    session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryQueryResponse:
    ok: bool
    records: list[MemoryRecord] = field(default_factory=list)
    error_code: str | None = None
    error_message: str = ""


@runtime_checkable
class MemoryProvider(Protocol):
    def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        ...

    def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        ...


class NullMemoryProvider:
    def write(self, request: MemoryWriteRequest) -> MemoryWriteResponse:
        return MemoryWriteResponse(
            ok=False,
            scope=request.scope,
            key=request.key,
            session_id=request.session_id,
            error_code="memory_unavailable",
            error_message="No memory provider configured.",
        )

    def query(self, request: MemoryQueryRequest) -> MemoryQueryResponse:
        del request
        return MemoryQueryResponse(
            ok=False,
            records=[],
            error_code="memory_unavailable",
            error_message="No memory provider configured.",
        )
