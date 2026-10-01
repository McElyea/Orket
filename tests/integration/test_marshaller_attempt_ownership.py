"""Integration: attempt/workload native work retains effects and admitted values."""
import asyncio
import json
from pathlib import Path

import pytest

from orket.application.interactions.context import InteractionContext
from orket.marshaller import attempt_runtime as attempts
from orket.marshaller.artifacts import MarshallerArtifacts, write_json_file
from orket.marshaller.contracts import RunRequest
from orket.marshaller.ledger import LedgerWriter
from orket.workloads import marshaller_v0 as workload
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.integration.test_marshaller_command_ownership import command_fixture
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.marshaller.test_runner import _read_ledger

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def attempt_fixture(first):
    _, repo, _, _, request_path, proposal_path = await asyncio.to_thread(command_fixture, first)
    request = RunRequest.model_validate_json(await asyncio.to_thread(request_path.read_text, encoding="utf-8"))
    proposal = json.loads(await asyncio.to_thread(proposal_path.read_text, encoding="utf-8"))
    artifacts = MarshallerArtifacts(first, "attempt-native")
    await artifacts.ensure_layout()
    runtime = attempts.AttemptRuntime(run_id="attempt-native", run_request=request,
        artifacts=artifacts, allowed_paths=["app.txt"])
    return runtime, LedgerWriter(artifacts.run_root / "ledger.jsonl"), proposal, repo


def hold_native(monkeypatch, owner, name, predicate, failure):
    hold, native = NativeHold(), getattr(owner, name)

    def held(*args, **kwargs):
        if hold.entered.is_set() or not predicate(*args, **kwargs):
            return native(*args, **kwargs)
        hold.wait()
        try:
            result = native(*args, **kwargs)
            if failure:
                raise OSError("controlled native attempt failure")
            return result
        finally:
            hold.finished.set()

    monkeypatch.setattr(owner, name, held)
    return hold


@pytest.mark.parametrize("phase", ["exists", "remove", "digest"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_attempt_native_lifetime(tmp_path, monkeypatch, phase, stop, failure, record_property):
    first, other = await roots(tmp_path)
    runtime, ledger, proposal, repo = await attempt_fixture(first)
    attempt = runtime.artifacts.attempt_dir(1)
    clone = attempt / "workspace_clone"
    assert clone.is_relative_to(first)
    await asyncio.to_thread(clone.mkdir, parents=True)
    await asyncio.to_thread((clone / "old.txt").write_text, "old clone", encoding="utf-8")
    if phase == "exists":
        hold = hold_native(monkeypatch, Path, "exists", lambda path: path == repo, failure)
    elif phase == "remove":
        hold = hold_native(monkeypatch, attempts.shutil, "rmtree", lambda path, *args: path == clone, failure)
    else:
        hold = hold_native(monkeypatch, attempts, "compute_tree_digest", lambda path: path == clone, failure)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            return await runtime.execute_attempt(ledger=ledger, attempt_index=1, proposal_payload=proposal)

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        assert await file_exists(attempt / "decision.json") == (stop == "none" and not failure)
        rows = await asyncio.to_thread(_read_ledger, ledger.ledger_path)
        assert [row["event_type"] for row in rows] == (["attempt_started", "attempt_completed"]
            if stop == "none" and not failure else ["attempt_started"])
        if phase == "remove" and (stop != "none" or failure):
            assert not await file_exists(clone)
        if phase == "digest":
            assert await asyncio.to_thread((clone / "app.txt").read_text, encoding="utf-8") == "promoted bytes\n"
        assert await asyncio.to_thread((repo / "app.txt").read_text, encoding="utf-8") == "hello\n"
        assert not await file_exists(other / "workspace")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)


async def test_attempt_captures_nested_proposal_and_owner_values(tmp_path, monkeypatch, record_property):
    first, other = await roots(tmp_path)
    runtime, ledger, proposal, _ = await attempt_fixture(first)
    attempt = runtime.artifacts.attempt_dir(1)
    hold = hold_stream(monkeypatch, attempt / "proposal.json", "write")
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            return await runtime.execute_attempt(ledger=ledger, attempt_index=1, proposal_payload=proposal)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        proposal["touched_paths"].append("forbidden.txt")
        runtime.allowed_paths = ("different.txt",)
        runtime.run_request.task_spec["gate_commands"]["test"] = ["absent-command"]
        runtime.artifacts.run_root = other / "redirected"
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        assert result.accept
        decision = json.loads(await asyncio.to_thread((attempt / "decision.json").read_text, encoding="utf-8"))
        assert decision["gate_results_normalized"][0]["passed"] is True
        assert not await file_exists(other / "redirected")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)


def real_file_context(root):
    async def emit(event, payload):
        await write_json_file(root / f"{event.value}.json", payload)
        return True

    async def commit(intent):
        await write_json_file(root / "commit.json", intent.model_dump(mode="json"))

    return InteractionContext(session_id="native-session", turn_id="native-turn", session_params={},
        packet1_context_envelope={}, packet1_provider_lineage=[], emit=emit, cancel_event=asyncio.Event(),
        commit_sink=commit)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_workload_captures_inputs_and_retains_resolution(tmp_path, monkeypatch, stop, failure, record_property):
    first, other = await roots(tmp_path)
    _, _, _, _, request, proposal = await asyncio.to_thread(command_fixture, first)
    monkeypatch.chdir(first)
    config = {"run_request_path": "request.json", "proposal_paths": ["proposal.json"], "workspace_root": ".",
        "run_id": "workload-native", "allowed_paths": ["app.txt"]}
    hold = hold_native(monkeypatch, Path, "resolve", lambda path, *args, **kwargs: path.name == request.name, failure)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            return await workload.run_marshaller_v0(input_config=config, turn_params={},
                interaction_context=real_file_context(first / "events"))

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        config.update(run_id="late-run", workspace_root=str(other))
        config["proposal_paths"][:] = [str(other / "absent.json")]
        config["allowed_paths"][:] = ["different.txt"]
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        run = first / "workspace/default/stabilizer/run/workload-native"
        assert await file_exists(run / "summary.json") == (stop == "none" and not failure)
        assert await file_exists(first / "events/commit.json") == (stop == "none" and not failure)
        if stop == "none" and not failure:
            assert result == {"post_finalize_wait_ms": 0}
            observed = json.loads(await asyncio.to_thread((run / "summary.json").read_text, encoding="utf-8"))
            assert observed["accepted"]
        assert not await file_exists(other / "workspace")
        assert await file_exists(proposal)
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
