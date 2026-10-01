"""Integration: admitted tool workers settle before runtime cancellation/deadline outcomes."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.adapters.tools import runtime
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/tool_runtime_worker.py"
CASES = [("sync", "success", stop) for stop in
         ("none", "cancel", "deadline", "deadline-repeated", "abandoned-waiter")]
CASES += [("sync", kind, stop) for kind in ("OSError", "CancelledError") for stop in ("cancel", "deadline")]
CASES += [("sync", "CancelledError", "none"), ("sync", "SystemExit", "none"),
          ("sync", "SystemExit", "cancel"), ("sync", "KeyboardInterrupt", "none"),
          ("sync", "BaseException", "cancel")]
CASES += [(route, "returned-exception", "none") for route in ("sync", "async")]
CASES += [("toolbox", "success", "cancel"), ("toolbox", "success", "deadline-repeated"),
          ("toolbox", "OSError", "deadline")]
CASES += [("async", "success", stop) for stop in ("deadline", "deadline-repeated", "cancel-then-deadline")]


@pytest.mark.parametrize("route,kind,stop", CASES)
async def test_tool_runtime_retains_real_effect_and_selected_outcome(tmp_path, route, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [route, kind, stop], record_property)
    assert (data["route"], data["kind"], data["stop"]) == (route, kind, stop)
    assert data["invoke_pending"] and data["tool_settled"] and data["native_calls"] == 1
    assert data["native_effect_observed"] and data["result_policy"] and data["healthy_followup"]
    assert data["task_settled_before_emergency"] and data["logging_scope_explicit"]
    assert data["returned_exception_value"] is (kind == "returned-exception")
    assert data["timeout_records"] == int(stop == "deadline" and kind in {"success", "returned-exception"})
    if route == "async":
        assert data["async_cancellations"] == int(stop != "none")
    if route == "toolbox":
        assert data["nomination_records"] == 1
    expected = await asyncio.to_thread(lambda: {"path": str(Path(runtime.__file__).resolve()),
        "sha256": hashlib.sha256(Path(runtime.__file__).read_bytes()).hexdigest()})
    assert data["runtime_source"] == expected
