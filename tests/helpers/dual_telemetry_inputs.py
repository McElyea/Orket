"""Physical dual-ledger and bounded native-log observations for integration proof."""
import asyncio
import json
import threading
from copy import deepcopy
from types import SimpleNamespace

from orket.application.services import dual_write_telemetry
from orket.runtime.evidence.run_ledger_factory import build_run_ledger_repository
from tests.helpers.dual_ledger import start_values

PARITY = "run_ledger_dual_write_parity"
DIAGNOSTIC = "telemetry_sink_error"


def factory(root, *, sink=None):
    return build_run_ledger_repository(mode="dual_write", db_path=root / "runtime.db",
        workspace_root=root / "runtime-workspace", telemetry_sink=sink)


async def read_records(path):
    def read():
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]
    return await asyncio.to_thread(read)


async def assert_durable_start(repo):
    sqlite = await repo.sqlite_repo.get_run("run")
    protocol = await repo.protocol_repo.get_run("run")
    assert sqlite["run_name"] == protocol["run_name"] == "original"
    assert sqlite["status"] == protocol["status"] == "running"
    events = await repo.protocol_repo.list_events("run")
    assert [row["kind"] for row in events] == ["run_started"]
    raw = await asyncio.to_thread(repo._intent_path.read_bytes)
    assert json.loads(raw)["pending"] == []


def fail_custom_sink(payload):
    raise RuntimeError("supplied telemetry sink refused")


def hold_real_log(monkeypatch, repo, target):
    state = SimpleNamespace(entered=threading.Event(), unblock=threading.Event(), finished=threading.Event(),
                            expired=False, worker=None, calls=0, borrowed=None, expected=None)
    actual_emit, actual_log = repo._telemetry.emit, dual_write_telemetry.log_event

    async def observe(payload):
        state.borrowed = payload
        return await actual_emit(payload)

    def held(event, data=None, **options):
        if event != target:
            return actual_log(event, data, **options)
        state.calls += 1
        state.worker = threading.get_ident()
        state.expected = deepcopy(data)
        state.entered.set()
        try:
            state.expired = not state.unblock.wait(5)
            if state.expired:
                raise TimeoutError("dual telemetry fixture hold expired")
            return actual_log(event, data, **options)
        finally:
            state.finished.set()

    monkeypatch.setattr(repo._telemetry, "emit", observe)
    monkeypatch.setattr(dual_write_telemetry, "log_event", held)
    return state


async def observe_public_start(repo, state, root, stop):
    task = asyncio.create_task(repo.start_run(**start_values()))
    try:
        assert await asyncio.to_thread(state.entered.wait, 5), "real native log route was not entered"
        assert state.worker != threading.get_ident() and not task.done()
        await asyncio.wait_for(assert_durable_start(repo), 2)
        state.borrowed["phase"] = "mutated-after-admission"
        state.borrowed["differences"].append({"late": ["mutation"]})
        repo._telemetry.workspace = root / "late-workspace"
        if stop == "cancel":
            task.cancel("first")
            await asyncio.sleep(0)
            task.cancel("second")
            await asyncio.sleep(0)
            assert not task.done()
    finally:
        state.unblock.set()
        result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 7)
    assert state.finished.is_set() and not state.expired and state.calls == 1
    if stop == "cancel":
        assert isinstance(result, asyncio.CancelledError)
    else:
        assert result is None


async def assert_workspace_record(root, event, expected):
    rows = await read_records(root / "runtime-workspace/orket.log")
    row, = [row for row in rows if row["event"] == event]
    payload = {key: value for key, value in row["data"].items() if key != "runtime_event"}
    assert payload == expected
    assert row["timestamp"].endswith("-07:00")
    assert not await asyncio.to_thread((root / "workspace/default/orket.log").exists)
    assert not await asyncio.to_thread((root / "late-workspace/orket.log").exists)


class HookedPayload(dict):
    calls = 0

    def __getitem__(self, key):
        self.calls += 1
        return super().__getitem__(key)


class HookedValue:
    calls = 0

    def __str__(self):
        self.calls += 1
        return "native conversion ran"
