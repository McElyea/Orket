from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter_ns
from uuid import uuid4


class RuntimeInputService:
    """Owns nondeterministic runtime inputs used by interactive/runtime hosts."""

    def create_session_id(self) -> str:
        return str(uuid4())[:8]

    def create_effect_owner_id(self) -> str:
        return str(uuid4())

    def create_flow_id(self) -> str:
        return f"FLOW-{uuid4().hex[:8].upper()}"

    def create_flow_revision_id(self) -> str:
        return f"frv_{uuid4().hex}"

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def utc_now_iso(self) -> str:
        return self.utc_now().isoformat()

    def monotonic_ns(self) -> int:
        """Observation clock; never use this value as a deterministic decision input."""
        # perf_counter is monotonic and avoids GetTickCount64's coarse resolution
        # on supported Windows Python 3.11/3.12 installations.
        return perf_counter_ns()
