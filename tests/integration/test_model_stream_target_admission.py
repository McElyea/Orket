"""Integration: actual blocked model observations cannot admit a builtin inference turn."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.workloads import model_stream_v1 as workload
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / "helpers/model_stream_admission_worker.py"
CASES = ["quarantined-openai", "quarantined-llama", "missing-gguf", "empty-gguf",
         "admitted-openai", "admitted-llama", "empty-model"]


@pytest.mark.parametrize("case", CASES)
async def test_model_stream_respects_actual_target_admission(tmp_path, case, record_property):
    data = await run_worker(tmp_path, WORKER, [case], record_property)
    assert data["case"] == case and data["refusal_policy_verified"] and data["observed_path"] == "primary"
    admitted = case.startswith("admitted-")
    assert data["admission"] == ("allowed" if admitted else "refused")
    assert data["observed_result"] == ("success" if admitted else "failure")
    if not admitted and case != "empty-model":
        assert data["nonempty_blocked"] and data["outcome_type"] == "ModelConnectionError"
    expected = await asyncio.to_thread(lambda: {"path": str(Path(workload.__file__).resolve()),
        "sha256": hashlib.sha256(Path(workload.__file__).read_bytes()).hexdigest()})
    assert data["workload_source"] == expected
