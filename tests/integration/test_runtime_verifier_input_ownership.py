"""Layer: integration. Real verifier command and native observation ownership."""
import asyncio
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.logging import settle_log_write_frontier
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_path,
    hold_stream,
    settle,
    timeout_while_held,
    wait_entered,
)
from tests.integration.test_verification_process_lifetime import (
    WORKER,
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_verifier_captures_nested_command_and_policy_before_observation(tmp_path, monkeypatch):
    command = [sys.executable, "-c", "print('{\"selected\":\"original\"}')"]
    issue = {"runtime_verifier": {"commands": [command], "expect_json_stdout": True,
                                 "json_assertions": [{"path": "selected", "op": "eq", "value": "original"}]}}
    organization = SimpleNamespace(process_rules={"runtime_verifier_timeout_sec": 10})
    verifier = RuntimeVerifier(tmp_path, organization=organization, issue_params=issue)
    hold = hold_path(monkeypatch, "exists", tmp_path / "agent_output")
    task = asyncio.create_task(verifier.verify())
    try:
        await wait_entered(hold)
        command[-1] = "print('{\"selected\":\"mutated\"}')"
        issue["runtime_verifier"]["json_assertions"][0]["value"] = "mutated"
        organization.process_rules["runtime_verifier_timeout_sec"] = 1
        hold.release.set()
        result = await task
        assert result.ok, result.errors
        assert json.loads(result.command_results[0]["stdout"]) == {"selected": "original"}
        assert result.command_results[0]["process_lifetime"]["cleanup_confirmed"]
    finally:
        await settle(task, hold)


async def test_verifier_metadata_retains_repeated_cancellation(tmp_path, monkeypatch, record_property):
    hold = hold_path(monkeypatch, "exists", tmp_path / "agent_output")
    task = asyncio.create_task(RuntimeVerifier(tmp_path).verify())
    try:
        await cancel_while_held(task, hold, tmp_path / "response.sqlite3", record_property)
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("operation", ["open", "read", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_verifier_syntax_stream_settles_before_interrupted_return(
    tmp_path, monkeypatch, record_property, operation, stop,
):
    target = tmp_path / "agent_output" / "main.py"
    await asyncio.to_thread(target.parent.mkdir)
    await asyncio.to_thread(target.write_text, "value = 42\n", encoding="utf-8")
    hold = hold_stream(monkeypatch, target, operation)
    task = asyncio.create_task(RuntimeVerifier(tmp_path).verify())
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_while_held
        await interrupt(task, hold, tmp_path / "response.sqlite3", record_property)
        assert hold.streams and all(stream.closed for stream in hold.streams)
    finally:
        await settle(task, hold)


async def test_verifier_captures_ambient_environment_and_relative_root(tmp_path, monkeypatch):
    selected, other = tmp_path / "selected", tmp_path / "other"
    await asyncio.to_thread(selected.mkdir)
    await asyncio.to_thread(other.mkdir)
    monkeypatch.chdir(selected)
    monkeypatch.setenv("ORKET_VERIFIER_CAPTURE_TEST", "original")
    command = [sys.executable, "-c", "import json,os;print(json.dumps({'value':os.environ['ORKET_VERIFIER_CAPTURE_TEST'],'cwd':os.getcwd()}))"]
    verifier = RuntimeVerifier(Path(), issue_params={"runtime_verifier": {"commands": [command]}})
    hold = hold_path(monkeypatch, "exists", selected / "agent_output")
    task = asyncio.create_task(verifier.verify())
    try:
        await wait_entered(hold)
        monkeypatch.chdir(other)
        monkeypatch.setenv("ORKET_VERIFIER_CAPTURE_TEST", "mutated")
        hold.release.set()
        result = await task
        assert result.ok, result.errors
        assert json.loads(result.command_results[0]["stdout"]) == {"value": "original", "cwd": str(selected)}
    finally:
        await settle(task, hold)


async def test_verifier_policy_commands_and_artifact_requirements_are_detached(tmp_path, monkeypatch):
    command = [sys.executable, "-c", "print('original')"]
    rules = {"runtime_verifier_commands": [command], "runtime_verifier_require_deployment_files": True,
             "runtime_verifier_required_deployment_files": ["required.txt"]}
    await asyncio.to_thread((tmp_path / "required.txt").write_text, "present", encoding="utf-8")
    verifier = RuntimeVerifier(tmp_path, organization=SimpleNamespace(process_rules=rules))
    hold = hold_path(monkeypatch, "exists", tmp_path / "agent_output")
    task = asyncio.create_task(verifier.verify())
    try:
        await wait_entered(hold)
        command[-1] = "print('mutated')"
        rules["runtime_verifier_required_deployment_files"][0] = "absent.txt"
        hold.release.set()
        result = await task
        assert result.ok, result.errors
        assert result.command_results[0]["stdout"].strip() == "original"
    finally:
        await settle(task, hold)


async def test_verifier_read_failure_during_cancel_stops_command_admission(tmp_path, monkeypatch):
    target = tmp_path / "agent_output/main.py"
    await asyncio.to_thread(target.parent.mkdir)
    await asyncio.to_thread(target.write_text, "value = 42\n", encoding="utf-8")
    command = [sys.executable, "-c", "from pathlib import Path;Path('unexpected-command.txt').write_text('ran')"]
    verifier = RuntimeVerifier(tmp_path, issue_params={"runtime_verifier": {"commands": [command]}})
    hold = hold_stream(monkeypatch, target, "read", failure=True)
    task = asyncio.create_task(verifier.verify())
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        hold.release.set()
        with pytest.raises(OSError, match="controlled native stream failure"):
            await task
        assert all(stream.closed for stream in hold.streams)
        assert not await asyncio.to_thread((tmp_path / "unexpected-command.txt").exists)
    finally:
        await settle(task, hold)


async def test_verifier_cancellation_log_uses_captured_invocation_root(tmp_path, monkeypatch):
    selected, later = tmp_path / "selected", tmp_path / "later"
    await asyncio.to_thread(selected.mkdir)
    await asyncio.to_thread(later.mkdir)
    monkeypatch.chdir(selected)
    command = [sys.executable, str(WORKER), str(selected), "2"]
    verifier = RuntimeVerifier(Path(), issue_params={"runtime_verifier": {"commands": [command]}})
    task = asyncio.create_task(verifier.verify())
    processes = []
    try:
        processes = await await_tree(selected)
        monkeypatch.chdir(later)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        await asyncio.to_thread(settle_log_write_frontier)
        await assert_stopped(processes, selected)
        assert await asyncio.to_thread((selected / "orket.log").is_file)
        assert not await asyncio.to_thread((later / "orket.log").exists)
        records = (await asyncio.to_thread((selected / "orket.log").read_text, encoding="utf-8")).splitlines()
        events = [json.loads(row) for row in records]
        assert [item["event"] for item in events] == ["verification_process_cancelled"]
        assert events[0]["data"]["cleanup_confirmed"]
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, selected)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_prior_handled_cancellation_does_not_reclassify_later_syntax_failure(tmp_path):
    target = tmp_path / "agent_output/main.py"
    await asyncio.to_thread(target.parent.mkdir)
    await asyncio.to_thread(target.write_text, "def broken(:\n", encoding="utf-8")

    async def invoke():
        asyncio.current_task().cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.sleep(0)
        organization = SimpleNamespace(process_rules={"runtime_verifier_commands": []})
        return await RuntimeVerifier(tmp_path, organization=organization).verify()

    result = await asyncio.create_task(invoke())
    assert not result.ok
    assert result.failure_breakdown == {"python_compile": 1}
    assert not result.command_results
