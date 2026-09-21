"""Typed results across real card/control-plane stores and native process cleanup."""
import asyncio
import json
import os
import sys

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.epic_dispatch_batch import run_epic_dispatch_batch
from orket.application.services.fixture_verification_service import FixtureVerificationUncertain
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus
from tests.helpers.card_completion import complete_existing_card
from tests.integration.test_epic_completion_publication import publication_pipeline

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_cancelled_epic_retains_open_authority_after_native_cleanup(test_root, workspace, db_path):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    marker = workspace / "child-started"

    async def workload(**kwargs):
        command = [sys.executable, "-c", "import pathlib,time,sys; pathlib.Path(sys.argv[1]).touch(); time.sleep(60)", str(marker)]
        await CommandProcessSupervisor(workspace, cancellation_event="verification_process_cancelled").run(command, cwd=workspace, environment=dict(os.environ), timeout_seconds=30)

    pipeline.orchestrator.execute_epic = workload
    task = asyncio.create_task(pipeline.run_card("publication_epic", session_id="cancelled", build_id="build"))
    try:
        async with asyncio.timeout(15):
            while not await asyncio.to_thread(marker.exists):
                if task.done():
                    pytest.fail(f"Execution stopped before native dispatch: {task.result()}")
                await asyncio.sleep(0.02)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(RuntimeExecutionCancelled) as stopped:
            await asyncio.wait_for(task, 15)
        observed = stopped.value.result
        assert observed.observation == "cancelled" and not observed.succeeded
        assert observed.run.lifecycle_state.value == "executing" and observed.final_truth is None
        assert stopped.value.__cause__.lifetime.cleanup_confirmed
        async with pipeline.epic_publication.repository.transaction("cancelled") as tx:
            assert (await tx.get_admission()).phase == "active"
            assert await tx.get() is None
        repeated = await pipeline.run_card("publication_epic", session_id="cancelled", build_id="build")
        assert repeated.observation == "unresolved" and "WORKLOAD_OUTCOME_UNCERTAIN" in repeated.reason
        assert repeated.run_id == observed.run_id
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pipeline.close()


@pytest.mark.parametrize("failed_member", [None, 1, 2])
# Layer: integration
async def test_collection_uses_distinct_retained_members_and_stops_on_failure(
    test_root, workspace, db_path, monkeypatch, failed_member,
):
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    model = test_root / "model/core"
    first = json.loads(await asyncio.to_thread((model / "epics/publication_epic.json").read_text, encoding="utf-8"))
    second = {**first, "name": "second_epic", "issues": [{**first["issues"][0], "id": "ISSUE-2"}]}
    await asyncio.to_thread((model / "epics/second_epic.json").write_text, json.dumps(second), encoding="utf-8")
    await asyncio.to_thread((model / "rocks").mkdir, exist_ok=True)
    collection = {"id": "group", "name": "group", "description": "Two independent epics", "epics": [
        {"epic": "publication_epic", "department": "core"}, {"epic": "second_epic", "department": "core"}]}
    await asyncio.to_thread((model / "rocks/group.json").write_text, json.dumps(collection), encoding="utf-8")
    created = []
    prepare = pipeline.pipeline_wiring_service.prepare_sub_pipeline

    async def prepare_member(**kwargs):
        construct = await prepare(**kwargs)

        def create_member():
            child = construct()
            index = len(created) + 1
            created.append(child)

            async def workload(**_kwargs):
                if index == failed_member:
                    await child.async_cards.update_status(f"ISSUE-{index}", CardStatus.CANCELED)
                else:
                    await complete_existing_card(child.async_cards, f"ISSUE-{index}", child.workspace,
                                                 service=child.runtime_context.card_completion)

            child.orchestrator.execute_epic = workload
            return child

        return create_member

    monkeypatch.setattr(pipeline.pipeline_wiring_service, "prepare_sub_pipeline", prepare_member)
    try:
        result = await pipeline.run_card("group", build_id="group-build", session_id="group-session")
        assert result.succeeded is (failed_member is None)
        assert len(result.members) == (failed_member or 2) and all(child._closed for child in created)
        assert [m.result.session_id for m in result.members] == [f"group-session-member-{i + 1}" for i in range(len(created))]
        assert len({member.result.run_id for member in result.members}) == len(created)
        assert all(isinstance(member.result, RuntimeExecutionResult) for member in result.members)
        assert ("group" in pipeline.bug_fix_manager.active_phases) is result.succeeded
    finally:
        await pipeline.close()


@pytest.mark.parametrize("reverse", [False, True])
# Layer: integration
async def test_parallel_uncertain_cleanup_cannot_publish_a_business_failure(test_root, workspace, db_path, reverse):
    """Real retained run/admission, with injected batch failures rather than a live daemon refusal."""
    pipeline = await publication_pipeline(test_root, workspace, db_path)
    errors = [ExecutionFailed("business failure"), FixtureVerificationUncertain({"cleanup_confirmed": False})]

    async def dispatch(error):
        await asyncio.sleep(0)
        raise error

    async def workload(**kwargs):
        await run_epic_dispatch_batch(errors[::-1] if reverse else errors, dispatch)

    pipeline.orchestrator.execute_epic = workload
    try:
        result = await pipeline.run_card("publication_epic", session_id="uncertain", build_id="build")
        assert result.observation == "unresolved" and not result.succeeded
        assert result.lifecycle_state.value == "executing" and result.final_truth is None
        assert "FixtureVerificationUncertain" in result.reason
        assert (await pipeline.run_ledger.get_run("uncertain"))["status"] == "running"
        async with pipeline.epic_publication.repository.transaction("uncertain") as tx:
            assert (await tx.get_admission()).phase == "active"
            assert await tx.get_outcome() is None and await tx.get() is None
    finally:
        await pipeline.close()
