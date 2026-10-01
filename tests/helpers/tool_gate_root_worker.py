"""Actual application validation, iDesign/AST and governed writes under root rotation."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services import tool_gate_service as gates
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.logging import bind_logging, prepare_logging
from orket.services.ast_validator import ASTValidator
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.application_root_controls import NativeHold, admitted, origins, prepare_trees, settle
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import public_caller


def install_gate_observation(gate, monkeypatch, hold, observations):
    native, policy = gate._file_write_facts, gate._policy.validate
    idesign, ast = gate.idesign_validator.validate_turn, ASTValidator.validate_code

    def held(*args, **kwargs):
        hold.wait()
        try:
            return native(*args, **kwargs)
        finally:
            hold.finished.set()

    def facts(*args, **kwargs):
        selected = kwargs["file_facts"]
        observations["facts"] = {"requested": selected.requested_path, "relative": selected.relative_path,
                                 "error": selected.error}
        return policy(*args, **kwargs)

    def design(turn, workspace):
        observations["idesign_root"] = str(workspace)
        return idesign(turn, workspace)

    def validate(content, filename):
        observations["ast_calls"] = observations.get("ast_calls", 0) + 1
        return ast(content, filename)

    monkeypatch.setattr(gate, "_file_write_facts", held)
    monkeypatch.setattr(gate._policy, "validate", facts)
    monkeypatch.setattr(gate.idesign_validator, "validate_turn", design)
    monkeypatch.setattr(ASTValidator, "validate_code", validate)


async def input_guard(first, kind):
    gate = gates.ToolGate(None, Path("C:relative"))
    if kind == "drive":
        result = await gate.validate("write_file", {"path": "x.txt"}, {}, [])
        assert isinstance(result, str) and result.startswith("Invalid file path: ")
        assert "DRIVE_RELATIVE_ROOT_UNSUPPORTED" in result
        assert await gate.validate("write_file", {}, {}, []) == "write_file requires 'path' argument"
        assert await gate.validate("create_issue", {"summary": "valid summary"}, {}, []) is None
    else:
        executor = GovernedAgentFileEffectExecutor(first / "workspace", tool_gate=gates.ToolGate(None, first / "workspace"))
        result = await executor.write(path="../outside.txt", content="refused", issue_id="issue")
        assert not result["ok"] and "Security violation" in result["error"]
        assert not await asyncio.to_thread((first / "outside.txt").exists)
    return {"input_refused": True, "path": "primary", "result": "success"}


async def observe(first, other, route, change, stop, monkeypatch):
    gate, hold, observations = gates.ToolGate(None, Path("workspace")), NativeHold(), {}
    install_gate_observation(gate, monkeypatch, hold, observations)
    target = first / "workspace/engines/test_engine.py"
    if route == "governed":
        executor = GovernedAgentFileEffectExecutor(first / "workspace", tool_gate=gate)
        operation = executor.write(path=str(target), content="class TestEngine: pass\n", issue_id="issue")
    else:
        code = "def broken(" if stop == "invalid-ast" else "class TestEngine: pass\n"
        operation = gate.validate("write_file", {"path": "engines/test_engine.py", "content": code},
                                  {"idesign_enabled": True}, ["developer"])
    active = asyncio.create_task(public_caller(operation))
    try:
        await admitted(hold, active)
        if change == "cwd":
            await asyncio.to_thread(os.chdir, other)
        else:
            gate.workspace_root = other / "workspace"
        if stop == "cancel":
            active.cancel("first gate interruption")
            await asyncio.sleep(0)
            active.cancel("later gate interruption")
        assert await sqlite_response(first / "responsive.sqlite3", lambda *args: None) < .5
        assert not active.done() and not hold.finished.is_set()
        hold.release.set()
        result = await asyncio.wait_for(active, 10)
        await settle(active, hold)
        observations.update(native_settled=hold.finished.is_set(), calls=hold.calls,
                            result_type=type(result).__name__, target_exists=await asyncio.to_thread(target.exists))
        await asyncio.to_thread(write_payload_with_diff_ledger, first.parent / "gate-after-settlement.json", observations)
        if route == "governed":
            assert result["ok"] and await asyncio.to_thread(target.read_text) == "class TestEngine: pass\n"
        elif stop == "cancel":
            assert type(result) is asyncio.CancelledError and result.args == ("first gate interruption",)
        elif stop == "invalid-ast":
            assert result.startswith("iDesign AST Violation:")
        else:
            assert result is None
        if route != "governed":
            assert observations["idesign_root"] == str(first / "workspace") and observations["ast_calls"] == 1
        if stop not in {"cancel", "invalid-ast"}:
            assert observations["facts"]["requested"] == str(target)
        assert not await asyncio.to_thread((other / "workspace/engines/test_engine.py").exists)
        assert hold.calls == 1 and hold.finished.is_set() and not hold.expired
        return {**observations, "selected_root": True, "path": "primary", "result": "success"}
    finally:
        await settle(active, hold)


async def exercise(root, route, change, stop):
    first, other = await asyncio.to_thread(prepare_trees, root)
    prepared = await prepare_logging(LoggingInputs(root, timezone_name="MST"))
    with pytest.MonkeyPatch.context() as monkeypatch, bind_logging(prepared):
        monkeypatch.chdir(first)
        result = await input_guard(first, change) if route == "input" else await observe(first, other, route, change, stop, monkeypatch)
    return {**result, "route": route, "change": change, "stop": stop}


def main():
    root = Path(sys.argv[1]).resolve()
    result = asyncio.run(exercise(root, *sys.argv[2:]))
    write_payload_with_diff_ledger(root / "result.json", {**result, **origins({"gate": gates})})


if __name__ == "__main__":
    main()
