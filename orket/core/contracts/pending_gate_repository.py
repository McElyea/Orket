from __future__ import annotations

from typing import Any, Protocol


class PendingGateRepository(Protocol):
    async def create_request(
        self,
        *,
        session_id: str,
        issue_id: str,
        seat_name: str,
        gate_mode: str,
        request_type: str,
        reason: str,
        payload: dict[str, Any] | None = None,
        created_at: str | None = None,
        request_id: str | None = None,
    ) -> str: ...

    async def resolve_request(
        self,
        *,
        request_id: str,
        status: str,
        resolution: dict[str, Any] | None = None,
        resolved_at: str | None = None,
        expected_status: str | None = None,
    ) -> bool: ...

    async def list_requests(
        self,
        *,
        session_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...
