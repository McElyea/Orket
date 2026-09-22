from __future__ import annotations

from datetime import UTC, datetime
from secrets import token_hex, token_urlsafe
from time import monotonic, perf_counter_ns
from uuid import uuid4


class RuntimeInputService:
    """Owns nondeterministic runtime inputs used by interactive/runtime hosts."""

    def create_session_id(self) -> str:
        return str(uuid4())[:8]

    def create_kernel_run_id(self) -> str:
        return f"run-{uuid4().hex[:8]}"

    def create_effect_owner_id(self) -> str:
        return str(uuid4())

    def create_flow_id(self) -> str:
        return f"FLOW-{uuid4().hex[:8].upper()}"

    def create_flow_revision_id(self) -> str:
        return f"frv_{uuid4().hex}"

    def create_card_id(self) -> str:
        return uuid4().hex

    def create_verification_scenario_id(self) -> str:
        return uuid4().hex[:4]

    def create_secret_token(self) -> str:
        """Capture a fresh secret at admission; callers must not publish it as evidence."""
        return token_urlsafe(32)

    def create_credential_token_id(self) -> str:
        return "tok-" + token_hex(12)

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def utc_now_iso(self) -> str:
        return self.utc_now().isoformat()

    def monotonic_seconds(self) -> float:
        """Elapsed-time observation in the coordinator lease clock's seconds domain."""
        return monotonic()

    def monotonic_ns(self) -> int:
        """Observation clock; never use this value as a deterministic decision input."""
        # perf_counter is monotonic and avoids GetTickCount64's coarse resolution
        # on supported Windows Python 3.11/3.12 installations.
        return perf_counter_ns()
