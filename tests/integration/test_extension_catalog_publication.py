"""Integration: independent catalog reads observe complete, admitted publications."""
from __future__ import annotations

import asyncio
import json
import threading

import pytest

from tests.helpers.extension_catalog_denial import deny_catalog_replace
from tests.integration.test_extension_installation_ownership import _installed

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_native_catalog_write_refusal_preserves_prior_bytes_and_checkout(tmp_path):
    source, manager, previous = await _installed(tmp_path)
    before = await asyncio.to_thread(manager.catalog_path.read_bytes)
    with deny_catalog_replace(manager.catalog_path), pytest.raises(OSError):
        await manager.install_from_repo(str(source))
    assert await asyncio.to_thread(manager.catalog_path.read_bytes) == before
    await asyncio.to_thread(manager._verify_extension_integrity, previous)


@pytest.mark.parametrize("payload", [[], {"extensions": {}}, {"extensions": [42]}])
async def test_malformed_catalog_cannot_be_silently_replaced(tmp_path, payload):
    source, manager, record = await _installed(tmp_path)
    raw = json.dumps(payload).encode()
    await asyncio.to_thread(manager.catalog_path.write_bytes, raw)
    with pytest.raises(ValueError, match="E_EXT_CATALOG_"):
        await manager.install_from_repo(str(source))
    assert await asyncio.to_thread(manager.catalog_path.read_bytes) == raw
    await asyncio.to_thread(manager._verify_extension_integrity, record)


async def test_interrupted_catalog_publication_retains_verified_effect(tmp_path, monkeypatch):
    source, manager, previous = await _installed(tmp_path)
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = manager.catalog._write_payload

    def held(payload):
        entered.set()
        try:
            assert release.wait(15)
            return original(payload)
        finally:
            settled.set()

    monkeypatch.setattr(manager.catalog, "_write_payload", held)
    task = asyncio.create_task(manager.install_from_repo(str(source)))
    try:
        assert await asyncio.to_thread(entered.wait, 12)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.1)
        assert not task.done() and not settled.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        current, = await asyncio.to_thread(manager.list_extensions)
        assert current.path != previous.path
        await asyncio.to_thread(manager._verify_extension_integrity, current)
        await asyncio.to_thread(manager._verify_extension_integrity, previous)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_installation_captures_source_policy_and_clock_before_allocation(tmp_path, monkeypatch):
    from orket.extensions import installation

    source, manager, _ = await _installed(tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = installation.allocate_checkout

    def held(root):
        entered.set()
        assert release.wait(10)
        return original(root)

    monkeypatch.setattr(installation, "allocate_checkout", held)
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "compat")
    monkeypatch.setattr(manager, "_utc_now", lambda: "2026-01-02T03:04:05+00:00")
    task = asyncio.create_task(manager.install_from_repo(str(source)))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
        monkeypatch.setattr(manager, "_utc_now", lambda: "2027-01-02T03:04:05+00:00")
        release.set()
        record = await asyncio.wait_for(task, 10)
        assert record.security_mode == "compat"
        assert record.installed_at_utc == "2026-01-02T03:04:05+00:00"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
