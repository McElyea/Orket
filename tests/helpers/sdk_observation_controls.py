"""Actual SDK child inputs, native lifetime publication and exact owner observations."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from orket.adapters.storage.sdk_workload_exchange import SdkWorkloadExchange
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.extensions import sdk_workload_runner
from tests.helpers.sdk_lifetime import sdk_request

EVENT = "sdk_workload_process_observed"
UNCERTAIN = "sdk_workload_process_uncertain"
SOURCE = """import json, os, time
from pathlib import Path
from orket_extension_sdk.result import WorkloadResult

def run(ctx, payload):
    root = Path(ctx.workspace_root)
    (root / "sdk-effect").write_text("executed")
    (root / "ready.tmp").write_text(json.dumps({"pid": os.getpid()}))
    (root / "ready.tmp").replace(root / "ready.json")
    deadline = time.monotonic() + 20
    while not (root / "release-sdk").exists() and time.monotonic() < deadline:
        time.sleep(.01)
    if payload["mode"] == "missing":
        os._exit(23)
    if payload["mode"] == "error":
        raise ValueError("controlled workload failure")
    return WorkloadResult(ok=True, output={"effect": "executed"})
"""


def prepare_request(root, mode):
    options = sdk_request(root, mode=mode)
    source = Path(options["extension"].path) / (options["workload"].entrypoint.split(":", 1)[0] + ".py")
    source.write_text(SOURCE, encoding="utf-8")
    return options


async def public_caller(operation):
    try:
        return await operation
    except BaseException as failure:
        # Exact public outcome only; an internal Task fatal escape still fails the isolated process.
        return failure


def observe_actual_owners(monkeypatch):
    state = SimpleNamespace(exchange=None, lifetime=None, reads=0, removes=0, selected=[], read_errors=[])
    prepare, read, remove = SdkWorkloadExchange.prepare, SdkWorkloadExchange.read_result, SdkWorkloadExchange.remove
    native = CommandProcessSupervisor.run
    initialize = sdk_workload_runner.SdkSubprocessExecutionUncertain.__init__

    def prepared(owner, request):
        result = prepare(owner, request)
        state.exchange = owner
        return result

    def read_result(owner):
        state.reads += 1
        try:
            return read(owner)
        except FileNotFoundError as failure:
            state.read_errors.append(failure)
            raise

    def removed(owner):
        state.removes += 1
        return remove(owner)

    async def executed(owner, argv, **options):
        result = await native(owner, argv, **options)
        if "orket.extensions.sdk_workload_subprocess" in argv:
            state.lifetime = result
        return result

    def selected(owner, *args):
        initialize(owner, *args)
        state.selected.append(owner)

    monkeypatch.setattr(SdkWorkloadExchange, "prepare", prepared)
    monkeypatch.setattr(SdkWorkloadExchange, "read_result", read_result)
    monkeypatch.setattr(SdkWorkloadExchange, "remove", removed)
    monkeypatch.setattr(CommandProcessSupervisor, "run", executed)
    monkeypatch.setattr(sdk_workload_runner.SdkSubprocessExecutionUncertain, "__init__", selected)
    return state


def assert_public_outcome(outcome, state, failure, cause, stop, mode, child_result):
    uncertain = failure is not None or mode == "missing"
    if uncertain:
        assert type(outcome) is sdk_workload_runner.SdkSubprocessExecutionUncertain, (
            "required native publication failure lost SDK uncertainty", type(outcome).__name__, state.removes)
        assert len(state.selected) == 1
        primary, = state.selected
        assert outcome is primary
        original = failure if failure is not None else state.read_errors[0]
        assert outcome.__cause__ is original and outcome.__context__ is original and outcome.__suppress_context__
        assert outcome.phase == ("lifetime-observation" if failure is not None else "result-read")
        assert outcome.lifetime is state.lifetime and outcome.exchange_path == state.exchange.root
        assert not hasattr(outcome, "diagnostic_error") and not getattr(outcome, "__notes__", [])
        assert state.reads == int(failure is None) and state.removes == 0
        if failure is not None:
            assert failure.__cause__ is cause
    elif stop != "none":
        assert type(outcome) is asyncio.CancelledError
        assert outcome.args == (("first later finalizer interruption",) if stop == "cancel" else ())
        assert state.reads == 0 and state.removes == 1 and not state.selected
    elif mode == "error":
        assert type(outcome) is sdk_workload_runner.SdkSubprocessRunError
        assert "controlled workload failure" in str(outcome)
        assert outcome.error_code == child_result["error_code"]
        assert outcome.capability_report == child_result["capability_report"]
        assert state.reads == state.removes == 1 and not state.selected
    else:
        assert type(outcome) is sdk_workload_runner.SdkSubprocessRunResult
        assert outcome.workload_result.ok and outcome.workload_result.output == {"effect": "executed"}
        assert outcome.capability_report == child_result["capability_report"]
        assert state.reads == state.removes == 1 and not state.selected
    return {"outcome_type": type(outcome).__name__, "native_cause_identity": True if failure is not None else None,
            "uncertainty": uncertain, "phase": outcome.phase if uncertain else None,
            "read_calls": state.reads, "remove_calls": state.removes, "result_adopted": not uncertain and stop == "none"}


async def read_records(path):
    def read():
        return [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
    return await asyncio.to_thread(read)
