"""Integration: real collection CLI failure retains its authored member workspace."""
import asyncio
import json
import os
import socket
import sys
from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL
from scripts.benchmarks.task_acceptance import verifier_for

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def unavailable_endpoint():
    # Reserve a local TCP port without listening: connection refusal, no external server.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield f"http://127.0.0.1:{reserved.getsockname()[1]}/v1"


@pytest.mark.asyncio
async def test_failed_collection_retains_member_evidence_without_a_generated_main(tmp_path, unavailable_endpoint):
    def prepare():
        task = json.loads((ROOT / "benchmarks/task_bank/v2_realworld/tasks.json").read_text(encoding="utf-8"))[0]
        path = tmp_path / "task.json"
        path.write_text(json.dumps(task), encoding="utf-8")
        return task, path

    task, path = await asyncio.to_thread(prepare)
    work, retained = tmp_path / "work", tmp_path / "retained"
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", ORKET_LLM_PROVIDER="llama_cpp",
                       ORKET_MODEL_PROVIDER="llama_cpp", ORKET_LLAMA_CPP_BASE_URL=unavailable_endpoint,
                       ORKET_LLM_LLAMA_CPP_BASE_URL=unavailable_endpoint, ORKET_MODULE_PROFILE="developer-local")
    environment.pop("PYTEST_CURRENT_TEST", None)
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="benchmark_failure_proof_cancelled")
    result = await owner.run(
        [sys.executable, str(ROOT / "scripts/benchmarks/live_rock_benchmark_runner.py"),
         "--task", str(path), "--run-dir", str(work), "--runs-root", str(retained), "--model", DEFAULT_LOCAL_MODEL],
        cwd=ROOT, environment=environment, timeout_seconds=45, output_limit_bytes=1024 * 1024,
    )
    assert result.reason == "completed" and result.returncode == 2
    assert result.cleanup_confirmed and result.capture_complete

    def inspect():
        reports = list(retained.glob("*/run_meta.json"))
        assert len(reports) == 1
        meta = json.loads(reports[0].read_text(encoding="utf-8"))
        member = work / meta["epic"]
        assert meta["effective_workspace"] == member.as_posix()
        assert not meta["validation_passed"] and meta["session_id"]
        assert not (member / "agent_output/main.py").exists()
        assert (member / "agent_output/benchmark_verify.py").read_text(encoding="utf-8") == verifier_for(task)
        assert "benchmark acceptance verifier missing or modified" not in meta["validation_issues"]
        assert (reports[0].parent / "orket.log").read_bytes() == (member / "orket.log").read_bytes()
        assert "result: failed" in (reports[0].parent / "live_runner_output.log").read_text(encoding="utf-8")

    await asyncio.to_thread(inspect)
