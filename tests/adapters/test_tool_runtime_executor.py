from __future__ import annotations

import asyncio

import pytest

from orket.adapters.tools.runtime import ToolRuntimeExecutor


@pytest.mark.asyncio
async def test_tool_runtime_executor_times_out_tool_call(tmp_path):
    """Layer: unit. Verifies per-tool-call timeout returns an explicit failure result."""

    async def _slow_tool(args, context=None):
        await asyncio.sleep(0.05)
        return {"ok": True}

    result = await ToolRuntimeExecutor().invoke(
        _slow_tool,
        {},
        context={"tool_name": "slow_tool"},
        tool_timeout_seconds=0.001,
        workspace=tmp_path,
    )

    assert result == {"ok": False, "error": "tool_timeout", "tool": "slow_tool"}


@pytest.mark.asyncio
async def test_tool_runtime_executor_runs_sync_tool_off_loop(tmp_path):
    """Layer: unit. Verifies synchronous tools still execute through the runtime seam."""

    def _sync_tool(args, context=None):
        return {"ok": True, "value": args["value"], "tool": context["tool_name"]}

    result = await ToolRuntimeExecutor().invoke(
        _sync_tool,
        {"value": 3},
        context={"tool_name": "sync_tool"},
        workspace=tmp_path,
    )

    assert result == {"ok": True, "value": 3, "tool": "sync_tool"}
