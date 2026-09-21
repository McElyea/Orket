"""CLI construction and diagnostic reads retain real native work through interruption."""
import asyncio
import sys
import threading
import time
from types import SimpleNamespace

import aiosqlite
import pytest

import orket.board as board_module
import orket.discovery as discovery_module
import orket.interfaces.cli as cli_module
from orket.orchestration.engine_services import ReplayDiagnosticsService
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def held_call(state, root, operation, *, failure):
    try:
        with (root / "model/core/epics/publication_epic.json").open("rb") as stream:
            state.files.append(stream)
            assert stream.read(1) == b"{"
            state.entered.set()
            assert state.release.wait(5), "CLI native read release deadline"
            if failure:
                (root / "missing-cli-input.json").read_bytes()
            return operation()
    finally:
        state.finished.set()


def install_boundaries(monkeypatch, root, state, stage, stop):
    original_engine = cli_module.OrchestrationEngine

    def create(workspace, department, **kwargs):
        kwargs.update(config_root=root, db_path=str(root / "cards.db"))
        if stage == "construction" and stop == "worker_failure":
            # A factory cannot recover an instance its callback allocates and
            # then throws away. This failure occurs before owner construction.
            return held_call(state, root, lambda: original_engine(workspace, department, **kwargs), failure=True)
        owner = original_engine(workspace, department, **kwargs)
        state.owners.append(owner)
        return held_call(state, root, lambda: owner, failure=stop == "worker_failure") if stage == "construction" else owner

    monkeypatch.setattr(cli_module, "OrchestrationEngine", create)
    if stage == "board":
        original = board_module.get_board_hierarchy
        monkeypatch.setattr(board_module, "get_board_hierarchy",
            lambda *a, **kw: held_call(state, root, lambda: original(*a, **kw), failure=stop == "worker_failure"))
    elif stage == "replay":
        original = ReplayDiagnosticsService.replay_turn_diagnostics
        monkeypatch.setattr(ReplayDiagnosticsService, "replay_turn_diagnostics",
            lambda *a, **kw: held_call(state, root, lambda: original(*a, **kw), failure=stop == "worker_failure"))
    elif stage == "manifest":
        original = cli_module.print_orket_manifest
        monkeypatch.setattr(cli_module, "print_orket_manifest",
            lambda *a, **kw: held_call(state, root, lambda: original(*a, **kw), failure=stop == "worker_failure"))
        monkeypatch.setattr(discovery_module, "get_installed_models", lambda: [])


@pytest.mark.parametrize("stage", ["construction", "board", "replay", "manifest"])
@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure"])
async def test_cli_runtime_io_is_responsive_and_owned(test_root, workspace, monkeypatch, record_property, stage, stop):
    await asyncio.to_thread(_write_epic_assets, test_root, "publication_epic")
    turn = workspace / "observability/cli-session/ISSUE/001_lead"
    await asyncio.to_thread(turn.mkdir, parents=True)
    await asyncio.to_thread((turn / "checkpoint.json").write_text, "{}", encoding="utf-8")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), files=[], owners=[])
    monkeypatch.chdir(test_root)
    monkeypatch.setattr(cli_module, "sys", SimpleNamespace(platform="fixture", stdout=sys.stdout, stderr=sys.stderr))
    monkeypatch.setattr(cli_module, "perform_first_run_setup",
                        lambda: {"reconciliation": "success", "onboarding": "no_op"})
    install_boundaries(monkeypatch, test_root, state, stage, stop)
    args = ["--workspace", str(workspace), *(["--replay-turn", "cli-session:ISSUE:1"] if stage == "replay"
                                           else ["--epic", "publication_epic"] if stage == "manifest" else ["--board"])]

    async def invoke():
        async with asyncio.timeout(5), asyncio.timeout(None) as deadline:
            state.deadline = deadline
            return await cli_module.run_cli(args)

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        async with asyncio.timeout(5):
            while not state.entered.is_set():
                if task.done():
                    await task
                    pytest.fail("CLI exited before reaching the native boundary")
                await asyncio.sleep(.001)
        if stop == "timeout":
            state.deadline.reschedule(asyncio.get_running_loop().time() + .05)
            record_property("deadline_epoch", "native-admission")
        async with aiosqlite.connect(workspace / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < .5
        if stop != "timeout":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(.08)
        assert not task.done() and not state.finished.is_set() and not state.files[0].closed
        assert all(not owner._closed for owner in state.owners)
        state.release.set()
        assert await asyncio.wait_for(task, 5) == (1 if stop == "worker_failure" else 130)
        assert all(owner._closed for owner in state.owners)
        assert bool(state.owners) == (stage != "construction" or stop != "worker_failure")
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
        for owner in state.owners:
            await owner.close()
    assert not timer.is_alive() and state.finished.is_set() and all(stream.closed for stream in state.files)


async def test_cli_entry_timeout_still_owns_startup_before_engine_creation(
    test_root, workspace, monkeypatch, record_property,
):
    await asyncio.to_thread(_write_epic_assets, test_root, "publication_epic")
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(),
                            finished=threading.Event(), files=[])
    constructed = []
    original_startup = cli_module.perform_first_run_setup

    def forbidden_engine(*args, **kwargs):
        constructed.append((args, kwargs))
        raise AssertionError("Expired startup must not construct an engine")

    monkeypatch.chdir(test_root)
    monkeypatch.setattr(cli_module, "sys", SimpleNamespace(platform="fixture", stdout=sys.stdout, stderr=sys.stderr))
    monkeypatch.setattr(cli_module, "OrchestrationEngine", forbidden_engine)
    monkeypatch.setattr(cli_module, "perform_first_run_setup",
                        lambda: held_call(state, test_root, original_startup, failure=False))

    async def invoke():
        async with asyncio.timeout(.05):
            return await cli_module.run_cli(["--board", "--workspace", str(workspace)])

    timer = threading.Timer(.8, state.release.set)
    timer.start()
    started = time.perf_counter()
    task = asyncio.create_task(invoke())
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        async with aiosqlite.connect(workspace / "responsive.sqlite3") as connection:
            assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
        elapsed = time.perf_counter() - started
        record_property("responsive_sqlite_seconds", elapsed)
        record_property("deadline_epoch", "cli-entry")
        assert elapsed < .5
        await asyncio.sleep(.08)
        assert not task.done() and not state.files[0].closed and not constructed
        state.release.set()
        assert await asyncio.wait_for(task, 5) == 130
    finally:
        state.release.set()
        timer.cancel()
        await asyncio.to_thread(timer.join, 5)
        await asyncio.gather(task, return_exceptions=True)
    assert not constructed and not timer.is_alive() and state.finished.is_set()
    assert all(stream.closed for stream in state.files)
