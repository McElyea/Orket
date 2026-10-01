"""Integration: marshaller public command reads/publications retain native work."""
import asyncio
import sys
from pathlib import Path

import pytest

from orket.marshaller import cli, promotion, replay
from orket.marshaller.canonical import hash_canonical_json
from orket.marshaller.equivalence import compute_equivalence_key
from tests.helpers.runtime_verification_hold import hold_stream
from tests.integration.test_governed_demo_ownership import file_exists, observe_held
from tests.integration.test_marshaller_publication_ownership import assert_outcome, roots
from tests.marshaller.test_cli import _write_json
from tests.marshaller.test_runner import _git, _init_repo, _make_patch, _proposal_payload, _run_request_payload

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def command_fixture(first):
    repo, revision = _init_repo(first)
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    proposal = _proposal_payload(revision, _make_patch(repo, "promoted bytes\n"))
    request = _run_request_payload(repo, {"test": [sys.executable, "-c", "print('actual gate')"]})
    request_path = _write_json(first / "request.json", request)
    proposal_path = _write_json(first / "proposal.json", proposal)
    run = first / "workspace/default/stabilizer/run/run"
    attempt = run / "attempts/1"
    _write_json(run / "run.json", {"run_id": "run", "request": request})
    _write_json(run / "summary.json", {"accepted_attempt_index": 1, "accepted": True, "attempt_count": 1})
    _write_json(attempt / "proposal.json", proposal)
    _write_json(attempt / "decision.json", {"accept": True, "policy_version": "v0", "gate_results_normalized": [],
        "equivalence_key": compute_equivalence_key(base_revision_digest=revision,
            proposal_digest=hash_canonical_json(proposal), policy_version="v0", gate_results_normalized=[])})
    for name in ["metrics", "apply_result", "checks/test"]:
        _write_json(attempt / f"{name}.json", {"observed": name})
    (attempt / "patch.diff").write_text(proposal["patch"], encoding="utf-8", newline="\n")
    return run, repo, branch, revision, request_path, proposal_path


@pytest.mark.parametrize("route,operation", [
    ("list", "read"), ("inspect", "close"), ("replay-read", "read"),
    ("replay-write", "write"), ("promote-read", "read"), ("promote-write", "close"),
])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_marshaller_command_native_lifetime(tmp_path, monkeypatch, route, operation, stop, failure, record_property):
    first, other = await roots(tmp_path)
    run, repo, branch, revision, _, _ = await asyncio.to_thread(command_fixture, first)
    selected = run / ({"list": "summary.json", "inspect": "attempts/1/proposal.json",
        "replay-read": "attempts/1/decision.json", "replay-write": "replay_result.json",
        "promote-read": "run.json", "promote-write": "promotion.json"}[route])
    hold = hold_stream(monkeypatch, selected, operation, failure=failure)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            if route == "list":
                return await cli.list_marshaller_runs(first)
            if route == "inspect":
                return await cli.inspect_marshaller_attempt(first, run_id="run")
            if route.startswith("replay"):
                return await replay.replay_run(run)
            return await promotion.promote_run(run, actor_id="user", actor_source="test", branch=branch)

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        assert_outcome(result, stop, failure)
        assert all(stream.closed for stream in hold.streams)
        assert not await file_exists(other / "workspace")
        committed = await asyncio.to_thread(_git, repo, "rev-parse", "HEAD")
        assert (committed != revision) == (route == "promote-write" or
                                          (route == "promote-read" and stop == "none" and not failure))
        if route == "promote-write" and (stop != "none" or failure):
            assert await file_exists(run / "promotion.json")
            assert not await file_exists(run / "ledger.jsonl")
        if route == "replay-read" and (stop != "none" or failure):
            assert not await file_exists(run / "replay_result.json")
        if stop == "none" and not failure and route.startswith("replay"):
            assert result["equivalence_key_match"]
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)


async def test_execute_captures_file_list_workspace_allowlist_and_actor(tmp_path, monkeypatch, record_property):
    first, other = await roots(tmp_path)
    _, repo, branch, _, request, proposal = await asyncio.to_thread(command_fixture, first)
    monkeypatch.chdir(first)
    monkeypatch.setenv("GIT_AUTHOR_NAME", "admitted actor")
    paths, allowed = [proposal.relative_to(first)], ["app.txt"]
    hold = hold_stream(monkeypatch, request, "read")
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            return await cli.execute_marshaller_from_files(workspace_root=Path(), run_request_path=request,
                proposal_paths=paths, allowed_paths=allowed, run_id="actual-command", promote=True, branch=branch)

    task = asyncio.create_task(dispatch())
    try:
        assert await asyncio.to_thread(hold.entered.wait, 3)
        paths[:] = [other / "absent.json"]
        allowed[:] = ["different.txt"]
        monkeypatch.setenv("GIT_AUTHOR_NAME", "late actor")
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        assert result["accept"] and result["promotion"]["actor_id"] == "admitted actor"
        assert Path(result["run_path"]).is_relative_to(first)
        assert await asyncio.to_thread((repo / "app.txt").read_text, encoding="utf-8") == "promoted bytes\n"
        assert not await file_exists(other / "workspace")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)


@pytest.mark.parametrize("route", ["list", "inspect", "replay", "promote"])
async def test_relative_command_roots_survive_later_cwd(tmp_path, monkeypatch, route, record_property):
    first, other = await roots(tmp_path)
    run, _, branch, _, _, _ = await asyncio.to_thread(command_fixture, first)
    monkeypatch.chdir(first)
    native = Path.exists
    from tests.helpers.application_root_controls import NativeHold
    hold = NativeHold()

    def held(path):
        if hold.entered.is_set():
            return native(path)
        hold.wait()
        try:
            return native(path)
        finally:
            hold.finished.set()

    # Promotion first reads run.json; the subsequent summary existence check is held.
    monkeypatch.setattr(Path, "exists", held)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(10), deadline:
            if route == "list":
                return await cli.list_marshaller_runs(Path())
            if route == "inspect":
                return await cli.inspect_marshaller_attempt(Path(), run_id="run")
            if route == "replay":
                return await replay.replay_run(run.relative_to(first))
            return await promotion.promote_run(run.relative_to(first), actor_id="user", actor_source="test", branch=branch)

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, "none", other, monkeypatch, record_property)
        assert not isinstance(result, BaseException), repr(result)
        if route == "list":
            assert [item["run_id"] for item in result] == ["run"]
        elif route == "replay":
            assert result["equivalence_key_match"]
        assert not await file_exists(other / "workspace")
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
