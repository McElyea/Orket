"""Own real run-ledger pipeline construction and cleanup for composed integration tests."""
from contextlib import AsyncExitStack

import pytest

from orket.adapters.storage.async_protocol_run_ledger import AsyncProtocolRunLedgerRepository
from orket.runtime.execution_pipeline import ExecutionPipeline
from tests.helpers.protocol_ledger_clock import ProtocolLedgerClock


@pytest.fixture
async def ledger_pipeline():
    async with AsyncExitStack() as owners:
        async def create(test_root, workspace, db_path, *, protocol=False):
            clock = ProtocolLedgerClock()
            repository = AsyncProtocolRunLedgerRepository(workspace, timestamp_factory=clock.utc_now_iso) if protocol else None
            return await owners.enter_async_context(ExecutionPipeline.open(
                workspace=workspace, department='core', db_path=db_path,
                config_root=test_root, run_ledger_repo=repository, runtime_inputs=clock))

        yield create
