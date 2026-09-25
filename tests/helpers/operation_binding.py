"""Physical fixtures for operation-record binding controls."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.contracts.protocol_hashing import build_step_id, derive_operation_id
from orket.core.domain import ClosureBasisClassification, ResultClass, RunState
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.turn_artifacts import (
    artifact_destination,
    artifact_test_utc_now,
    execute_executor_dispatch_fixture,
)

__test__ = False

SESSION = "operation-binding"
ISSUE = "ISSUE-BINDING"
ROLE = "developer"
TURN = 1
RUN_ID = f"turn-tool-run:{SESSION}:{ISSUE}:{ROLE}:0001"
ATTEMPT_ID = f"{RUN_ID}:attempt:0001"
ARGS = {"path": "agent_output/out.txt", "content": "effect-a"}
IMMUTABLE_NAMES = (
    "control_plane",
    "control_plane_wal",
    "control_plane_shm",
    "operation",
    "receipt",
    "effect",
)
LOCAL_PREFIX_NAMES = ("parsed_calls", "checkpoint")


class ControlledModel:
    def __init__(self, proposals: list[dict[str, Any]]) -> None:
        self.proposals = proposals
        self.calls = 0

    async def complete(self, _messages):  # type: ignore[no-untyped-def]
        self.calls += 1
        proposed = self.proposals[min(self.calls - 1, len(self.proposals) - 1)]
        payload = {"content": "", "tool_calls": [proposed]}
        return {"content": json.dumps(payload), "total_tokens": self.calls}


class PhysicalToolbox:
    def __init__(self, workspace: Path, *, fail: bool = False) -> None:
        self.files = AsyncFileTools(workspace)
        self.fail = fail
        self.calls = 0

    async def execute(self, tool_name, args, context=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        if tool_name == "write_file":
            await self.files.write_file(str(args["path"]), str(args.get("content") or ""))
            payload = {"ok": not self.fail, "tool": tool_name, "touched_paths": [str(args["path"])]}
            if self.fail:
                payload["error"] = "controlled tool failure"
            return payload
        if tool_name == "read_file":
            return {"ok": True, "tool": tool_name, "content": await self.files.read_file(str(args["path"]))}
        raise AssertionError(f"unexpected physical tool call: {tool_name}")


class AfterToolProbe:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def after_tool(self, tool_name, args, result, **_kwargs):  # type: ignore[no-untyped-def]
        self.calls.append((str(tool_name), dict(args)))
        return MiddlewareOutcome(replacement=result)


def proposal(tool: str = "write_file", args: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"tool": tool, "args": dict(ARGS if args is None else args)}


def issue() -> IssueConfig:
    return IssueConfig(id=ISSUE, summary="Bind operation truth", seat=ROLE, status=CardStatus.IN_PROGRESS)


def role() -> RoleConfig:
    return RoleConfig(
        id="DEV",
        summary=ROLE,
        description="Exercise operation binding",
        tools=["write_file", "read_file"],
    )


def context(*, replay: bool = False, resume: bool = False) -> dict[str, object]:
    return {
        "session_id": SESSION,
        "issue_id": ISSUE,
        "role": ROLE,
        "roles": [ROLE],
        "current_status": "in_progress",
        "selected_model": "controlled",
        "turn_index": TURN,
        "history": [],
        "protocol_governed_enabled": True,
        "protocol_replay_mode": replay,
        "resume_mode": resume,
    }


def operation_id() -> str:
    return derive_operation_id(
        run_id=SESSION,
        step_id=build_step_id(issue_id=ISSUE, turn_index=TURN),
        tool_index=0,
    )


def make_case(
    tmp_path: Path,
    proposals: list[dict[str, Any]],
    *,
    fail: bool = False,
) -> SimpleNamespace:
    workspace = tmp_path / "workspace"
    database = tmp_path / "control-plane.sqlite3"
    service = build_turn_tool_control_plane_service(database)
    probe = AfterToolProbe()
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=workspace),
        workspace=workspace,
        middleware=TurnLifecycleInterceptors([probe]),
        control_plane_service=service,
        utc_now=artifact_test_utc_now,
    )
    return SimpleNamespace(
        workspace=workspace,
        database=database,
        service=service,
        executor=executor,
        model=ControlledModel(proposals),
        toolbox=PhysicalToolbox(workspace, fail=fail),
        issue=issue(),
        role=role(),
        probe=probe,
    )


def destination(case):  # type: ignore[no-untyped-def]
    return artifact_destination(
        case.executor.artifact_writer,
        session_id=SESSION,
        issue_id=ISSUE,
        role_name=ROLE,
        turn_index=TURN,
    )


async def captured_destination(case):  # type: ignore[no-untyped-def]
    return await asyncio.to_thread(destination, case)


def _dump(record: Any) -> Any:
    return None if record is None else record.model_dump(mode="json")


async def control_plane_state(case) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    run = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    attempts = await case.service.execution_repository.list_attempt_records(run_id=RUN_ID)
    step = await case.service.execution_repository.get_step_record(step_id=operation_id())
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    truth = await case.service.publication.repository.get_final_truth(run_id=RUN_ID)
    checkpoint = await case.service.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{ATTEMPT_ID}"
    )
    current = next((row for row in attempts if row.attempt_id == ATTEMPT_ID), None)
    decision = None if current is None or current.recovery_decision_id is None else (
        await case.service.publication.repository.get_recovery_decision(
            decision_id=current.recovery_decision_id
        )
    )
    reservation = await case.service.publication.repository.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=RUN_ID)
    )
    lease = await case.service.publication.repository.get_latest_lease_record(
        lease_id=lease_id_for_run(run_id=RUN_ID)
    )
    return {
        "run": _dump(run),
        "attempts": [_dump(row) for row in attempts],
        "step": _dump(step),
        "effects": [_dump(row) for row in effects],
        "truth": _dump(truth),
        "checkpoint": _dump(checkpoint),
        "decision": _dump(decision),
        "reservation": _dump(reservation),
        "lease": _dump(lease),
    }


def _paths_sync(case) -> dict[str, Path]:  # type: ignore[no-untyped-def]
    selected = destination(case)
    database = case.database
    return {
        "control_plane": database,
        "control_plane_wal": Path(f"{database}-wal"),
        "control_plane_shm": Path(f"{database}-shm"),
        "operation": case.executor.artifact_writer.operation_result_path(
            destination=selected,
            operation_id=operation_id(),
        ),
        "receipt": selected.file_path("protocol_receipts.log"),
        "effect": case.workspace / str(ARGS["path"]),
        "parsed_calls": selected.file_path("parsed_tool_calls.json"),
        "checkpoint": selected.file_path("checkpoint.json"),
    }


async def artifact_paths(case) -> dict[str, Path]:  # type: ignore[no-untyped-def]
    return await asyncio.to_thread(_paths_sync, case)


def _read_optional(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


async def file_bytes(case, name: str) -> bytes | None:  # type: ignore[no-untyped-def]
    selected = (await artifact_paths(case))[name]
    return await asyncio.to_thread(_read_optional, selected)


async def physical_names(case, names) -> dict[str, dict[str, object] | None]:  # type: ignore[no-untyped-def]
    paths = await artifact_paths(case)
    observed: dict[str, dict[str, object] | None] = {}
    for name in names:
        content = await asyncio.to_thread(_read_optional, paths[name])
        observed[name] = None if content is None else {
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return observed


async def immutable_physical(case) -> dict[str, dict[str, object] | None]:  # type: ignore[no-untyped-def]
    return await physical_names(case, IMMUTABLE_NAMES)


async def local_prefix(case) -> dict[str, dict[str, object] | None]:  # type: ignore[no-untyped-def]
    return await physical_names(case, LOCAL_PREFIX_NAMES)


async def operation_record(case) -> dict[str, Any] | None:  # type: ignore[no-untyped-def]
    selected = await captured_destination(case)
    return await asyncio.to_thread(
        case.executor.artifact_writer.load_operation_result,
        destination=selected,
        operation_id=operation_id(),
    )


async def write_operation(case, payload: dict[str, Any] | str) -> None:  # type: ignore[no-untyped-def]
    path = (await artifact_paths(case))["operation"]
    relative = path.relative_to(case.workspace).as_posix()
    content = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=False)
    await AsyncFileTools(case.workspace).write_file(relative, content)


async def write_legacy_result(case, *, args, result) -> None:  # type: ignore[no-untyped-def]
    selected = await captured_destination(case)
    await asyncio.to_thread(
        case.executor.artifact_writer.persist_tool_result,
        destination=selected,
        tool_name="write_file",
        tool_args=args,
        result=result,
    )


async def legacy_result_physical(case, args):  # type: ignore[no-untyped-def]
    selected = await captured_destination(case)
    path = await asyncio.to_thread(
        case.executor.artifact_writer.tool_result_path,
        destination=selected,
        tool_name="write_file",
        tool_args=args,
    )
    content = await asyncio.to_thread(_read_optional, path)
    return None if content is None else {
        "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
    }


def mutate_record(record: dict[str, Any], mutation: str) -> dict[str, Any]:
    changed = json.loads(json.dumps(record))
    if mutation == "operation_id":
        changed["operation_id"] = "wrong-operation"
    elif mutation == "tool":
        changed["tool"] = "read_file"
    elif mutation == "args":
        changed["args"] = {**ARGS, "content": "effect-b"}
    elif mutation == "args_bool_int":
        changed["args"]["mode"] = 1
    elif mutation == "result":
        changed["result"] = {**changed["result"], "tampered": True}
    elif mutation == "digest":
        changed["result_digest"] = "0" * 64
    elif mutation == "missing_digest":
        changed.pop("result_digest", None)
    elif mutation == "malformed_digest":
        changed["result_digest"] = {"invalid": True}
    else:
        raise AssertionError(f"unknown operation mutation: {mutation}")
    return changed


async def seed_terminal(case, *, success: bool) -> SimpleNamespace:  # type: ignore[no-untyped-def]
    result = await case.executor.execute_turn(
        case.issue,
        case.role,
        case.model,
        case.toolbox,
        context(),
        system_prompt="SYSTEM",
    )
    state = await control_plane_state(case)
    stored = await operation_record(case)
    observed = await immutable_physical(case)
    proposed = case.model.proposals[0]
    assert result.success is success
    assert state["run"]["lifecycle_state"] == (RunState.COMPLETED if success else RunState.FAILED_TERMINAL).value
    assert state["truth"]["result_class"] == (ResultClass.SUCCESS if success else ResultClass.FAILED).value
    assert state["truth"]["closure_basis"] == ClosureBasisClassification.NORMAL_EXECUTION.value
    assert stored is not None and stored["operation_id"] == operation_id()
    assert stored["tool"] == proposed["tool"] and stored["args"] == proposed["args"]
    assert stored["result_digest"] == case.executor.artifact_writer.hash_payload(stored["result"])
    assert all(observed[name] is not None for name in ("control_plane", "operation", "receipt", "effect"))
    return SimpleNamespace(result=result, state=state, operation=stored)


def observe_reentry_and_forbid_owner(case, monkeypatch):  # type: ignore[no-untyped-def]
    reentries: list[dict[str, object]] = []
    owner_calls: list[str] = []
    original = case.service.ensure_reentry_allowed

    async def observed(**kwargs):  # type: ignore[no-untyped-def]
        reentries.append(dict(kwargs))
        return await original(**kwargs)

    def forbidden(run_id):  # type: ignore[no-untyped-def]
        owner_calls.append(str(run_id))
        raise AssertionError("embedded replay acquired the execution owner")

    monkeypatch.setattr(case.service, "ensure_reentry_allowed", observed)
    monkeypatch.setattr(case.service.execution_owners, "hold", forbidden)
    return reentries, owner_calls


def expected_reentry() -> dict[str, object]:
    return {"session_id": SESSION, "issue_id": ISSUE, "role_name": ROLE, "turn_index": TURN}


async def before_after(case, operation):  # type: ignore[no-untyped-def]
    before_state = await control_plane_state(case)
    before_files = await immutable_physical(case)
    result = await operation()
    after_state = await control_plane_state(case)
    after_files = await immutable_physical(case)
    return result, before_state, after_state, before_files, after_files


async def dispatch(case, proposed: dict[str, Any], *, resume: bool = False):  # type: ignore[no-untyped-def]
    turn = ExecutionTurn(
        timestamp=None,
        role=ROLE,
        issue_id=ISSUE,
        content="",
        tool_calls=[ToolCall(tool=proposed["tool"], args=dict(proposed["args"]))],
    )
    return await execute_executor_dispatch_fixture(
        case.executor,
        turn=turn,
        toolbox=case.toolbox,
        context=context(resume=resume),
        issue=case.issue,
    )
