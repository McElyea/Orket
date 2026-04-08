from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


class RuntimeInputService:
    """Owns nondeterministic runtime inputs used by interactive/runtime hosts."""

    def create_session_id(self) -> str:
        return str(uuid4())[:8]

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def utc_now_iso(self) -> str:
        return self.utc_now().isoformat()
