from __future__ import annotations

import hashlib
import json
from pathlib import Path

from orket.application.services.sandbox_lifecycle_event_service import SandboxLifecycleEventService
from orket.core.domain.sandbox_lifecycle_records import SandboxLifecycleEventRecord


class SandboxLifecycleEventPublisher:
    """Publishes deterministic sandbox lifecycle events through the durable event service."""

    def __init__(self, *, repository, spool_path: str | Path | None = None) -> None:
        resolved_spool = (
            Path(spool_path)
            if spool_path is not None
            else Path(repository.db_path).with_name("sandbox_lifecycle_events.spool.jsonl")
        )
        self.event_service = SandboxLifecycleEventService(
            repository=repository,
            spool_path=resolved_spool,
        )

    async def emit(
        self,
        *,
        sandbox_id: str | None,
        created_at: str,
        event_type: str,
        payload: dict[str, object],
        event_kind: str = "lifecycle",
    ) -> str:
        return await self.event_service.emit(
            SandboxLifecycleEventRecord(
                event_id=self._event_id(
                    sandbox_id=sandbox_id,
                    created_at=created_at,
                    event_type=event_type,
                    payload=payload,
                ),
                sandbox_id=sandbox_id,
                event_kind=event_kind,
                event_type=event_type,
                created_at=created_at,
                payload=payload,
            )
        )

    @staticmethod
    def _event_id(
        *,
        sandbox_id: str | None,
        created_at: str,
        event_type: str,
        payload: dict[str, object],
    ) -> str:
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(
            f"{sandbox_id or 'global'}:{event_type}:{created_at}:{blob}".encode("utf-8")
        ).hexdigest()
        return f"{event_type}:{digest}"
