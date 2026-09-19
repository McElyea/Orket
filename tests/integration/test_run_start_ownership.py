"""Real epic bootstrap drains its filesystem worker before reporting interruption."""
import asyncio
import json
import threading

import pytest

import orket.runtime.evidence.run_start_artifacts as artifacts
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from tests.application.test_execution_pipeline_run_ledger import _pipeline, _write_epic_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True], ids=["published", "worker-failure"])
async def test_bootstrap_worker_settles_before_interruption_truth(
    test_root, workspace, db_path, monkeypatch, stop, failure
):
    """Layer: integration. Controlled storage delay/failure, actual pipeline, artifacts and retained stores."""
    await asyncio.to_thread(_write_epic_assets, test_root, "bootstrap_owned")
    pipeline = _pipeline(test_root, workspace, db_path, protocol=True)
    entered, release, settled = threading.Event(), threading.Event(), threading.Event()
    original = artifacts._resolve_workspace_state_snapshot
    observed = {}

    def held_snapshot(**kwargs):
        result = original(**kwargs)
        observed["now"] = kwargs["now"]
        entered.set()
        try:
            assert release.wait(10), "Proof driver must release its worker"
            if failure:
                raise OSError("controlled bootstrap storage failure")
            return result
        finally:
            settled.set()

    monkeypatch.setattr(artifacts, "_resolve_workspace_state_snapshot", held_snapshot)
    operation = asyncio.create_task(pipeline.run_card(
        "bootstrap_owned", build_id="owned-build", session_id="owned-bootstrap"))
    request = operation
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        started = asyncio.get_running_loop().time()
        await asyncio.to_thread((workspace / "responsive").write_text, "ready", encoding="utf-8")
        assert asyncio.get_running_loop().time() - started < 0.5
        if stop == "timeout":
            # Start the deadline after entry; startup itself is outside this proof's timing bound.
            request = asyncio.create_task(asyncio.wait_for(operation, 0.01))
        else:
            request.cancel()
            await asyncio.sleep(0)
            request.cancel()
        await asyncio.sleep(0.1)
        assert not request.done() and not settled.is_set()
        assert operation.cancelling() == (1 if stop == "timeout" else 2)
        release.set()
        _, pending = await asyncio.wait([request], timeout=5)
        assert not pending
        try:
            result = request.result()
        except (asyncio.CancelledError, TimeoutError) as exc:
            result = exc
        assert settled.is_set()
        parent = workspace / "observability/owned-bootstrap"
        if failure:
            assert not isinstance(result, BaseException) and not result.succeeded
            assert result.observation == "unresolved" and "controlled bootstrap storage failure" in result.reason
            assert (parent / "runtime_contracts_staging").is_dir() and not (parent / "runtime_contracts").exists()
        else:
            # wait_for wraps the subtype on Python 3.11 and propagates it on 3.12.
            expected = RuntimeExecutionCancelled if stop == "cancel" else (TimeoutError, RuntimeExecutionCancelled)
            assert isinstance(result, expected) and operation.cancelled()
            if isinstance(result, RuntimeExecutionCancelled):
                assert result.result.observation == "cancelled" and not result.result.succeeded
            assert not (parent / "runtime_contracts_staging").exists()
            identity = json.loads(await asyncio.to_thread((parent / "runtime_contracts/run_identity.json").read_bytes))
            assert identity["start_time"] == observed["now"].isoformat()
        assert await pipeline.run_ledger.get_run("owned-bootstrap") is None
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(request, return_exceptions=True), 5)
        await pipeline.close()
