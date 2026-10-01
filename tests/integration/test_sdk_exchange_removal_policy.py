"""Integration: actual SDK execution and exchange cleanup retain truthful outcomes."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.extensions import sdk_workload_runner
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/sdk_removal_worker.py"
CASES = [("runner", kind, "none", "success", "before") for kind in
         ("PermissionError", "ValueError", "CancelledError", "SystemExit", "KeyboardInterrupt", "BaseException")]
CASES += [("runner", kind, "cancel", "success", "before") for kind in
          ("CancelledError", "SystemExit", "KeyboardInterrupt", "BaseException")]
CASES += [("runner", "success", stop, mode, "before") for mode in ("success", "error")
          for stop in ("none", "cancel", "timeout")]
CASES += [("runner", "CancelledError", "cancel", "error", "before"),
          ("runner", "ValueError", "none", "success", "partial"),
          ("runner", "CancelledError", "cancel", "success", "after"),
          ("runner", "success", "cancel", "ambient", "before")]
CASES += [("manager", kind, "none", "success", "before") for kind in ("ValueError", "CancelledError")]


@pytest.mark.parametrize("route,kind,stop,mode,stage", CASES)
async def test_sdk_exchange_removal_preserves_native_policy(tmp_path, route, kind, stop, mode, stage, record_property):
    data = await run_worker(tmp_path, WORKER, [route, kind, stop, mode, stage], record_property)
    assert (data["route"], data["kind"], data["stop"], data["mode"], data["stage"]) == (route, kind, stop, mode, stage)
    assert data["caller_cancel_requests"] == {"none": 0, "cancel": 2, "timeout": 1}[stop]
    uncertain = kind != "success"
    assert data["uncertainty"] is uncertain and data["native_failure_identity"] is uncertain
    assert data["physical_uncertainty_count"] == int(uncertain)
    assert data["selected_body_identity"] is (mode == "error")
    assert data["exchange_exists"] is (uncertain and stage != "after")
    assert data["request_retained"] is (uncertain and stage == "before")
    assert data["result_retained"] is (uncertain and stage != "after")
    assert data["caller_policy_preserved"] and data["read_calls"] == data["remove_calls"] == 1
    assert data["task_settled_before_emergency"] and data["logging_binding_restored"]
    assert data["lifetime"]["cleanup_confirmed"] and data["lifetime"]["capture_complete"]
    assert all(row["status"] in {"absent", "reused"} for row in data["processes_before_release"].values())
    assert await asyncio.to_thread(Path(data["exchange_path"]).exists) is data["exchange_exists"]
    if route == "manager":
        assert data["control_plane"]["final_truth_present"] is False
        assert data["control_plane"]["run_state"] == "executing"
    expected = await asyncio.to_thread(lambda: {"path": str(Path(sdk_workload_runner.__file__).resolve()),
        "sha256": hashlib.sha256(Path(sdk_workload_runner.__file__).read_bytes()).hexdigest()})
    assert data["source_origins"][sdk_workload_runner.__name__] == expected
    child = Path(sdk_workload_runner.__file__).with_name("sdk_workload_subprocess.py").resolve()
    assert data["child_source"] == {"path": str(child),
        "sha256": await asyncio.to_thread(lambda: hashlib.sha256(child.read_bytes()).hexdigest())}
