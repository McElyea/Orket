"""Layer: integration. Actual result artifacts and SQLite with controlled worker interruption."""
import asyncio
import threading
from copy import deepcopy

import pytest

from orket.core.contracts.protocol_hashing import hash_canonical_json
from tests.helpers.tool_result_persistence import ResultCase, enter, held_worker
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
async def test_tool_result_captures_all_publication_inputs_before_first_await(tmp_path, protocol):
    case = ResultCase(tmp_path, protocol)
    case.context["unrelated_live_owner"] = threading.Lock()
    await case.admit()
    async with held_worker(case, "operation") as (entered, release, _):
        task = asyncio.create_task(case.persist())
        try:
            await enter(entered)
            case.mutate()
        finally:
            release.set()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert outcome == "turn-tool-result:operation-1"
    operation, secondary = await case.artifacts()
    assert operation["args"] == case.expected[0]
    assert operation["result"] == case.expected[1]
    assert operation["result_digest"] == hash_canonical_json(case.expected[1])
    if protocol:
        assert secondary["tool_args"] == case.expected[0]
        assert secondary["execution_result"] == case.expected[1]
        assert secondary["validator_duration_ms"] == 1.25
        assert secondary["execution_capsule"] == case.expected[4]
        assert secondary["tool_invocation_manifest"]["declared_namespace_scopes"] == ["issue:ISSUE-1"]
        digest = secondary.pop("receipt_digest")
        assert digest == hash_canonical_json(secondary)
    else:
        assert secondary == case.expected[1]
    steps, effects = await case.records()
    assert len(steps) == len(effects) == 1
    assert steps[0].output_ref == "turn-tool-result:operation-1"
    assert "MUTATED" not in steps[0].model_dump_json() + effects[0].model_dump_json()


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
@pytest.mark.parametrize("stage", ["operation", "secondary"])
@pytest.mark.parametrize("interrupt", ["cancel", "timeout"])
@pytest.mark.parametrize("fail", [False, True], ids=["write", "write-then-error"])
async def test_tool_result_retains_worker_until_settled(tmp_path, protocol, stage, interrupt, fail):
    case = ResultCase(tmp_path, protocol)
    await case.admit()
    deadlines = []

    async def invoke():
        async with asyncio.timeout(None) as deadline:
            deadlines.append(deadline)
            return await case.persist()

    async with held_worker(case, stage, fail=fail) as (entered, release, finished):
        task = asyncio.create_task(invoke())
        try:
            await enter(entered)
            start = asyncio.get_running_loop().time()
            await asyncio.sleep(0.01)
            assert asyncio.get_running_loop().time() - start < 0.5
            if interrupt == "timeout":
                deadlines[0].reschedule(asyncio.get_running_loop().time() + 0.01)
                await asyncio.sleep(0.03)
            else:
                for _ in range(3):
                    task.cancel()
                    await asyncio.sleep(0.01)
            escaped = task.done()
            assert not finished.is_set()
            steps, effects = await case.records()
            assert steps[0].output_ref is None and not effects
        finally:
            release.set()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert not escaped, "caller returned while its admitted file worker could still write"
    assert finished.is_set()
    expected = OSError if fail else (TimeoutError if interrupt == "timeout" else asyncio.CancelledError)
    assert isinstance(outcome, expected)
    steps, effects = await case.records()
    assert steps[0].output_ref is None and not effects
    assert await asyncio.to_thread((case.directory / "operations/operation-1.json").is_file)


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
@pytest.mark.parametrize("stage", ["operation", "secondary"])
async def test_tool_result_worker_failure_cannot_publish_success(tmp_path, protocol, stage):
    case = ResultCase(tmp_path, protocol)
    await case.admit()
    async with held_worker(case, stage, fail=True) as (entered, release, finished):
        task = asyncio.create_task(case.persist())
        try:
            await enter(entered)
        finally:
            release.set()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(outcome, OSError) and finished.is_set()
    steps, effects = await case.records()
    assert steps[0].output_ref is None and not effects


@pytest.mark.parametrize("cancel", [False, True], ids=["captured", "cancelled"])
async def test_ordinary_result_without_control_plane_retains_its_worker(tmp_path, cancel):
    case = ResultCase(tmp_path, False, governed=False)
    await case.admit()
    async with held_worker(case, "secondary") as (entered, release, finished):
        task = asyncio.create_task(case.persist())
        try:
            await enter(entered)
            case.mutate()
            if cancel:
                task.cancel()
                await asyncio.sleep(0.02)
            escaped = task.done()
        finally:
            release.set()
            outcome, = await asyncio.gather(task, return_exceptions=True)
    assert not escaped and finished.is_set()
    assert isinstance(outcome, asyncio.CancelledError) if cancel else outcome is None
    cached = await asyncio.to_thread(case.writer.load_replay_tool_result, **case.identity,
        tool_name="write_file", tool_args=case.expected[0], resume_mode=True)
    assert cached == case.expected[1]
    assert not await asyncio.to_thread((case.directory / "operations").exists)
    assert not await asyncio.to_thread((tmp_path / "control-plane.sqlite3").exists)


@pytest.mark.parametrize("protocol", [False, True], ids=["ordinary", "protocol"])
async def test_concurrent_result_publications_keep_independent_captured_inputs(tmp_path, protocol):
    first, second = ResultCase(tmp_path / "first", protocol), ResultCase(tmp_path / "second", protocol)
    second.args["content"] = "second publication"
    second.result["nested"]["values"] = ["second"]
    second.expected = deepcopy((second.args, second.result, second.binding, second.context, second.capsule))
    await asyncio.gather(first.admit(), second.admit())
    async with held_worker(first, "operation") as a, held_worker(second, "operation") as b:
        tasks = [asyncio.create_task(case.persist()) for case in (first, second)]
        try:
            await asyncio.gather(enter(a[0]), enter(b[0]))
            first.mutate()
            second.mutate()
        finally:
            a[1].set()
            b[1].set()
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
    assert outcomes == ["turn-tool-result:operation-1"] * 2
    for case in (first, second):
        operation, _ = await case.artifacts()
        assert operation["args"] == case.expected[0] and operation["result"] == case.expected[1]
        steps, effects = await case.records()
        assert len(steps) == len(effects) == 1 and steps[0].output_ref == "turn-tool-result:operation-1"
