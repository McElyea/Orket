"""Integration: actual SDK child effects and required publication failure authority."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.extensions import sdk_workload_runner
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/sdk_observation_worker.py"
CASES = [("success", stop, "success") for stop in ("none", "cancel", "timeout")]
CASES += [(kind, stop, "success") for kind in
          ("PermissionError", "CancelledError", "SystemExit", "KeyboardInterrupt", "BaseException")
          for stop in ("none", "cancel")]
CASES += [("success", "none", mode) for mode in ("error", "missing")]


@pytest.mark.parametrize("kind,stop,mode", CASES)
async def test_sdk_required_observation_preserves_unadopted_result(tmp_path, kind, stop, mode, record_property):
    data = await run_worker(tmp_path, WORKER, [kind, stop, mode], record_property)
    assert (data["kind"], data["stop"], data["mode"]) == (kind, stop, mode)
    assert data["caller_cancel_requests"] == {"none": 0, "cancel": 2, "timeout": 1}[stop]
    uncertain = kind != "success" or mode == "missing"
    assert data["uncertainty"] is uncertain and data["exchange_retained"] is uncertain
    assert data["physical_uncertainty_records"] == int(uncertain)
    assert data["physical_observed_record"] and data["public_workspace_capture_retained"]
    assert data["native_cause_identity"] is (True if kind != "success" else None)
    assert data["task_settled_before_emergency"] and data["logging_binding_restored"]
    assert data["lifetime"]["cleanup_confirmed"] and data["lifetime"]["capture_complete"]
    assert all(row["status"] in {"absent", "reused"} for row in data["processes_before_release"].values())
    assert await asyncio.to_thread(Path(data["exchange_path"]).exists) is uncertain
    expected = await asyncio.to_thread(lambda: {
        "path": str(Path(sdk_workload_runner.__file__).resolve()),
        "sha256": hashlib.sha256(Path(sdk_workload_runner.__file__).read_bytes()).hexdigest()})
    assert data["source_origins"][sdk_workload_runner.__name__] == expected
    child = Path(sdk_workload_runner.__file__).with_name("sdk_workload_subprocess.py").resolve()
    assert data["child_source"] == {"path": str(child),
        "sha256": await asyncio.to_thread(lambda: hashlib.sha256(child.read_bytes()).hexdigest())}
