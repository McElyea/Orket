from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path

import pytest

from orket.adapters.storage.async_executor_service import AsyncExecutorService
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.adapters.storage.driver_resource_store import DriverResourceStore
from orket.driver_support_resources import DriverResourceMixin


class _DriverResourceHarness(DriverResourceMixin):
    def _operator_workspace_root(self) -> Path:
        return self.fs.workspace_root


@pytest.mark.asyncio
async def test_run_coroutine_blocking_rejects_running_loop_usage() -> None:
    """Layer: contract. Verifies the sync bridge fails closed instead of blocking an active event loop."""
    service = AsyncExecutorService()
    with pytest.raises(RuntimeError, match="cannot be used from a running event loop"):
        service.run_coroutine_blocking(asyncio.sleep(0))


@pytest.mark.asyncio
async def test_execute_structural_change_keeps_native_files_off_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Layer: integration. Real structural storage reads and writes stay in the owned worker."""
    model_root = tmp_path / "model"
    epic_path = model_root / "core" / "epics" / "billing.json"
    await asyncio.to_thread(epic_path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(epic_path.write_text, json.dumps({"name": "billing", "issues": []}), encoding="utf-8")
    harness = _DriverResourceHarness()
    harness.model_root, harness.fs = model_root, AsyncFileTools(tmp_path)
    observed, loop_thread = [], threading.get_ident()
    read, write = DriverResourceStore.read, DriverResourceStore.write

    def observe_read(store, path):
        observed.append(("read", threading.get_ident()))
        return read(store, path)

    def observe_write(store, path, payload):
        observed.append(("write", threading.get_ident()))
        return write(store, path, payload)

    monkeypatch.setattr(DriverResourceStore, "read", observe_read)
    monkeypatch.setattr(DriverResourceStore, "write", observe_write)
    result = await harness._execute_structural_change({
        "action": "create_issue", "target_parent": "billing", "suggested_department": "core",
        "new_asset": {"summary": "Add truth check", "seat": "coder", "priority": "High"},
    })
    saved = json.loads(await asyncio.to_thread(epic_path.read_text, encoding="utf-8"))
    assert result.startswith("Added issue 'Add truth check'")
    assert saved["issues"][0]["summary"] == "Add truth check"
    assert [action for action, _ in observed] == ["read", "write"]
    assert all(thread != loop_thread for _, thread in observed)
