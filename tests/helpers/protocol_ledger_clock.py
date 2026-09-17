"""Explicit wall-clock inputs for protocol publication fixtures."""
from datetime import UTC, datetime, timedelta

from orket.application.services.runtime_input_service import RuntimeInputService


class ProtocolLedgerClock(RuntimeInputService):
    def __init__(self):
        # Explicit synthetic inputs for bootstrap/ledger/publication, not measured duration.
        self.current = datetime(2026, 1, 1, tzinfo=UTC)

    def utc_now(self):
        observed = self.current
        self.current += timedelta(seconds=1)
        return observed

    def rewind(self):
        self.current -= timedelta(hours=1)
