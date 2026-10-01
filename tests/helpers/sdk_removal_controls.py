"""Actual SDK exchange deletion, selected child errors and installed-manager controls."""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import threading
from functools import partial
from pathlib import Path

from orket.extensions import sdk_workload_runner
from orket.extensions.git_commands import run_git
from orket.extensions.manager import ExtensionManager
from tests.helpers.sdk_observation_controls import prepare_request, public_caller


def removal_failure(kind):
    if kind == "success":
        return None
    failure = {"PermissionError": PermissionError("controlled SDK removal refusal"),
        "ValueError": ValueError("controlled SDK removal callback refusal"),
        "CancelledError": asyncio.CancelledError("native SDK removal cancellation"),
        "SystemExit": SystemExit(67), "KeyboardInterrupt": KeyboardInterrupt("native SDK removal fatal"),
        "BaseException": BaseException("native SDK removal base failure")}[kind]
    failure.__cause__ = LookupError("original native removal cause")
    return failure


class RemovalHold:
    def __init__(self, state, stage, failure):
        self.state, self.stage, self.failure = state, stage, failure
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.worker, self.expired = 0, None, False

    def install(self, monkeypatch):
        actual = shutil.rmtree

        def held(path, *args, **kwargs):
            if self.state.exchange is None or Path(path) != self.state.exchange.root:
                return actual(path, *args, **kwargs)
            self.calls += 1
            self.worker = threading.get_ident()
            self.entered.set()  # Actual adapter identity checks already passed before rmtree.
            try:
                self.expired = not self.release.wait(10)
                assert not self.expired, "SDK native removal hold was not released"
                if self.stage == "partial":
                    (Path(path) / "request.json").unlink()
                if self.stage == "after" or self.failure is None:
                    result = actual(path, *args, **kwargs)
                if self.failure is not None:
                    raise self.failure
                return result
            finally:
                self.finished.set()

        monkeypatch.setattr(shutil, "rmtree", held)


def observe_adoption(monkeypatch, state):
    state.body_error, state.adopted = None, None
    actual = sdk_workload_runner._adopt_result

    def adopted(raw, lifetime):
        try:
            state.adopted = actual(raw, lifetime)
            return state.adopted
        except sdk_workload_runner.SdkSubprocessRunError as failure:
            state.body_error = failure
            raise

    monkeypatch.setattr(sdk_workload_runner, "_adopt_result", adopted)


def prepare_files(root, mode):
    options = prepare_request(root, mode)
    source_root = Path(options["extension"].path)
    source = source_root / (options["workload"].entrypoint.split(":", 1)[0] + ".py")
    text = source.read_text(encoding="utf-8")
    text = text.replace('    root = Path(ctx.workspace_root)\n',
        '    root = Path(ctx.workspace_root)\n    (root / "sdk-run-id").write_text(ctx.run_id)\n')
    source.write_text(text, encoding="utf-8")
    return options


def write_manifest(options):
    extension, workload = options["extension"], options["workload"]
    root = Path(extension.path)
    (root / "extension.json").write_text(json.dumps({"manifest_version": "v0",
        "extension_id": extension.extension_id, "extension_version": "1.0.0",
        "allowed_stdlib_modules": list(extension.allowed_stdlib_modules),
        "workloads": [{"workload_id": workload.workload_id, "entrypoint": workload.entrypoint,
                       "required_capabilities": []}]}), encoding="utf-8")
    return root


async def prepare_operation(root, route, mode):
    options = await asyncio.to_thread(prepare_files, root, "success" if mode == "ambient" else mode)
    if route == "runner":
        return sdk_workload_runner.run_sdk_workload_in_subprocess(**options)
    source = await asyncio.to_thread(write_manifest, options)
    for args in [["init"], ["add", "."], ["-c", "user.email=test@example.com", "-c", "user.name=Test",
                                      "commit", "-m", "fixture"]]:
        await run_git(args, cwd=source, environment=dict(os.environ), timeout_seconds=10, code="E_FIXTURE_GIT")
    manager = await asyncio.to_thread(partial(ExtensionManager, catalog_path=root / "catalog.json",
        project_root=root, invocation_root=root, environment=dict(os.environ)))
    await manager.install_from_repo(str(source))
    return manager.run_workload(workload_id="fixture", input_config=options["input_payload"],
                                workspace=root, department="core")


async def call_with_ambient_exception(operation):
    try:
        raise LookupError("unrelated awaiting caller exception")
    except LookupError:
        return await public_caller(operation)


def assert_removal_outcome(outcome, state, failure, cause, stop, mode, child_result):
    if failure is not None:
        assert type(outcome) is sdk_workload_runner.SdkSubprocessExecutionUncertain, (
            "native exchange failure lost typed SDK uncertainty", type(outcome).__name__)
        assert state.selected == [outcome] and outcome.phase == "exchange-remove"
        assert outcome.__cause__ is failure and outcome.__context__ is failure and outcome.__suppress_context__
        assert failure.__cause__ is cause
        assert outcome.lifetime is state.lifetime and outcome.exchange_path == state.exchange.root
        assert not hasattr(outcome, "diagnostic_error") and not getattr(outcome, "__notes__", [])
        if mode == "error":
            assert failure.__context__ is state.body_error
    elif mode == "error":
        assert outcome is state.body_error and type(outcome) is sdk_workload_runner.SdkSubprocessRunError
        assert outcome.error_code == child_result["error_code"]
        assert outcome.capability_report == child_result["capability_report"]
        assert "controlled workload failure" in str(outcome)
        assert not state.selected
    elif stop != "none":
        assert type(outcome) is asyncio.CancelledError
        assert outcome.args == (("first later finalizer interruption",) if stop == "cancel" else ())
        assert not state.selected
    else:
        assert outcome is state.adopted and type(outcome) is sdk_workload_runner.SdkSubprocessRunResult
        assert outcome.workload_result.ok and outcome.workload_result.output == {"effect": "executed"}
        assert outcome.capability_report == child_result["capability_report"] and not state.selected
    assert state.reads == state.removes == 1
    return {"uncertainty": failure is not None, "outcome_type": type(outcome).__name__,
        "native_failure_identity": failure is not None, "selected_body_identity": mode == "error",
        "read_calls": state.reads, "remove_calls": state.removes, "caller_policy_preserved": True}


def remaining_bytes(exchange):
    return {"exists": exchange.exists(), "request": (exchange / "request.json").read_bytes()
            if (exchange / "request.json").exists() else None,
            "result": (exchange / "result.json").read_bytes() if (exchange / "result.json").exists() else None}
