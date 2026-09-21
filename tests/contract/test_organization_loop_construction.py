"""Synchronous organization construction refuses before reading on the event loop."""
import asyncio

import pytest

from orket.organization_loop import OrganizationLoop

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]


async def test_sync_organization_construction_refuses_before_file_access(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match='E_ORGANIZATION_LOOP_ASYNC_CREATE_REQUIRED'):
        OrganizationLoop()
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
