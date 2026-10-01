"""Integration: public model-stream workload admission through real local HTTP and commits."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.workloads import model_stream_v1 as workload
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/model_stream_input_worker.py"
CASES = ["control", "request", "api-key", "inference-timeout", "turn-timeout", "resolver-context", "empty-target"]


@pytest.mark.parametrize("case", CASES)
async def test_model_stream_admission_keeps_request_and_provider_inputs(tmp_path, case, record_property):
    data = await run_worker(tmp_path, WORKER, [case], record_property)
    assert data["case"] == case and data["path"] == "primary" and data["result"] == "success"
    if case == "empty-target":
        assert data["empty_target_refused"]
    else:
        assert data["admitted_inputs_used"] and data["real_catalog_and_completion"] and data["durable_commit_verified"]
    expected = await asyncio.to_thread(lambda: {"path": str(Path(workload.__file__).resolve()),
        "sha256": hashlib.sha256(Path(workload.__file__).read_bytes()).hexdigest()})
    assert data["workload_source"] == expected
