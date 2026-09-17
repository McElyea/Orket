"""Wake authority remains readable while its renewal waits for a terminal writer."""
from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.governed_agent_supervisor import GovernedAgentWakeClaimGuard
from tests.integration.test_async_governed_agent_wake_repository import _request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('reader_owner', ['shared', 'new'])
# Layer: integration
async def test_terminal_transaction_checks_wake_authority_during_renewal(tmp_path, monkeypatch, reader_owner):
    db = tmp_path / 'agent.sqlite3'
    repository = AsyncGovernedAgentWakeRepository(db)
    await repository.enqueue(_request())
    claim = await repository.claim_next(owner_id='owner', now_utc='2026-09-07T12:00:01Z',
                                       lease_expires_at_utc='2026-09-07T12:01:00Z', max_active_claims=1)
    authority = claim.authority
    assert authority is not None
    reader = repository if reader_owner == 'shared' else AsyncGovernedAgentWakeRepository(db)
    guard = GovernedAgentWakeClaimGuard(repository=reader, authority=authority, now_utc=lambda: '2026-09-07T12:00:02Z')
    renewal_entered = asyncio.Event()
    original_execute = aiosqlite.Connection.execute

    def observe_begin(connection, sql, parameters=None):
        if sql == 'BEGIN IMMEDIATE' and asyncio.current_task().get_name() == 'contended-renewal':
            renewal_entered.set()
        return original_execute(connection, sql, parameters)

    monkeypatch.setattr(aiosqlite.Connection, 'execute', observe_begin)
    renewal = None
    try:
        async with SQLiteControlPlaneTransactions(db)():
            renewal = asyncio.create_task(repository.renew_claim(
                authority=authority, now_utc='2026-09-07T12:00:02Z', lease_expires_at_utc='2026-09-07T12:02:00Z',
            ), name='contended-renewal')
            await asyncio.wait_for(renewal_entered.wait(), 2)
            # Bound established before measurement; SQLite's writer timeout is five seconds.
            await asyncio.wait_for(guard.ensure_active(), 1)
            assert not renewal.done()
    finally:
        if renewal is not None:
            transition = await asyncio.wait_for(renewal, 7)
            assert transition.status == 'applied'
    assert await repository.validate_claim(authority=authority, now_utc='2026-09-07T12:00:03Z')
    assert not await repository.validate_claim(authority=authority, now_utc='2026-09-07T12:02:00Z')
