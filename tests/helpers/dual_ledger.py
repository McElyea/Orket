"""Explicit backend and clock inputs for dual-ledger integration proof."""
import asyncio

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.dual_write_run_ledger import AsyncDualModeLedgerRepository
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock


def repositories(root, *, database="runtime.db", sqlite_type=AsyncRunLedgerRepository):
    sqlite = sqlite_type(root / database)
    protocol = AsyncProtocolRunLedgerRepository(root / "protocol", timestamp_factory=ProtocolLedgerClock().utc_now_iso)
    return AsyncDualModeLedgerRepository(sqlite_repo=sqlite, protocol_repo=protocol)

def start_values(name="original"):
    return dict(session_id="run", run_type="epic", run_name=name, department="core", build_id="b",
                summary={"nested": {"value": "original"}}, artifacts={"source": "original"})

class HeldSQLite(AsyncRunLedgerRepository):
    hold_after_commit = False

    def __init__(self, path):
        super().__init__(path)
        self.entered, self.release = asyncio.Event(), asyncio.Event()

    async def start_run(self, **kwargs):
        if self.hold_after_commit:
            await super().start_run(**kwargs)
        self.entered.set()
        await self.release.wait()
        if not self.hold_after_commit:
            await super().start_run(**kwargs)


class CommittedHeldSQLite(HeldSQLite):
    hold_after_commit = True
