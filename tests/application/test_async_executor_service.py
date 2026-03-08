from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_executor_service import AsyncExecutorService
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.driver_support_resources import DriverResourceMixin


class _DriverResourceHarness(DriverResourceMixin):
    pass


@pytest.mark.asyncio
async def test_run_coroutine_blocking_rejects_running_loop_usage() -> None:
    """Layer: contract. Verifies the sync bridge fails closed instead of blocking an active event loop."""
    service = AsyncExecutorService()
    with pytest.raises(RuntimeError, match="cannot be used from a running event loop"):
        service.run_coroutine_blocking(asyncio.sleep(0))


@pytest.mark.asyncio
async def test_execute_structural_change_uses_async_file_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Layer: integration. Verifies async structural changes do not fall back to sync file bridges."""
    model_root = tmp_path / "model"
    epic_path = model_root / "core" / "epics" / "billing.json"
    epic_path.parent.mkdir(parents=True, exist_ok=True)
    epic_path.write_text(json.dumps({"name": "billing", "issues": []}, indent=2), encoding="utf-8")

    harness = _DriverResourceHarness()
    harness.model_root = model_root
    harness.fs = AsyncFileTools(tmp_path)
    monkeypatch.setattr(harness.fs, "read_file_sync", lambda _path: (_ for _ in ()).throw(AssertionError("unexpected sync read")))
    monkeypatch.setattr(
        harness.fs,
        "write_file_sync",
        lambda _path, _content: (_ for _ in ()).throw(AssertionError("unexpected sync write")),
    )
    monkeypatch.setattr("orket.driver_support_resources.log_event", lambda *_args, **_kwargs: None)

    result = await harness._execute_structural_change(
        {
            "action": "create_issue",
            "target_parent": "billing",
            "suggested_department": "core",
            "new_asset": {"summary": "Add truth check", "seat": "coder", "priority": "High"},
        }
    )

    saved = json.loads(epic_path.read_text(encoding="utf-8"))
    assert result.startswith("Added issue 'Add truth check'")
    assert saved["issues"][0]["summary"] == "Add truth check"
