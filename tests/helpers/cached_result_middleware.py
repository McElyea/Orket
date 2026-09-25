"""Live leaf composition for cached-result middleware fixtures."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from functools import partial
from typing import Any

from orket.application.workflows.turn_tool_dispatcher_control_plane import (
    finalize_execution_if_needed,
    prepare_dispatch_if_needed,
)
from orket.application.workflows.turn_tool_dispatcher_protocol import load_or_execute_tool
from orket.application.workflows.turn_tool_dispatcher_support import build_execution_capsule
from orket.application.workflows.turn_tool_result_persistence import (
    persist_non_protocol_tool_result_if_needed,
    persist_protocol_operation,
)
from orket.core.contracts.protocol_hashing import (
    VALIDATOR_VERSION,
    build_step_id,
    default_protocol_hash,
    default_tool_schema_hash,
    derive_step_seed,
)
from orket.core.domain.execution import ExecutionTurn, ToolCall
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    RUN_ID,
    SESSION,
    TURN,
    captured_destination,
    context,
    operation_id,
    proposal,
)

__test__ = False


def _turn(case: Any) -> ExecutionTurn:
    selected = proposal()
    return ExecutionTurn(
        timestamp=None,
        role=str(case.role.name),
        issue_id=str(case.issue.id),
        content="",
        tool_calls=[ToolCall(tool=selected["tool"], args=deepcopy(selected["args"]))],
    )


def _context(*, protocol_enabled: bool) -> dict[str, Any]:
    return {
        **context(resume=True),
        "protocol_governed_enabled": protocol_enabled,
    }


async def compose_legacy_cached_result_leaf(
    case: Any,
    *,
    protocol_enabled: bool,
) -> tuple[ExecutionTurn, object]:
    """Exercise leaf owners; this is not public resume admission or acceptance."""
    turn = _turn(case)
    operation = _compose_leaf(
        case,
        turn=turn,
        fixture_context=_context(protocol_enabled=protocol_enabled),
        protocol_enabled=protocol_enabled,
    )
    outcome = (await asyncio.gather(operation, return_exceptions=True))[0]
    return turn, outcome


async def observe_cached_result_load_leaf(
    case: Any,
    *,
    protocol_enabled: bool,
) -> tuple[ExecutionTurn, object]:
    """Observe only the owned cache load and governed replay-anchor boundary."""
    turn = _turn(case)
    fixture_context = _context(protocol_enabled=protocol_enabled)
    destination = await captured_destination(case)
    step_id = build_step_id(issue_id=turn.issue_id, turn_index=TURN)
    operation = _load_cached_result(
        case,
        turn=turn,
        destination=destination,
        fixture_context=fixture_context,
        protocol_enabled=protocol_enabled,
        step_id=step_id,
    )
    outcome = (await asyncio.gather(operation, return_exceptions=True))[0]
    return turn, outcome


async def _compose_leaf(
    case: Any,
    *,
    turn: ExecutionTurn,
    fixture_context: dict[str, Any],
    protocol_enabled: bool,
) -> None:
    destination = await captured_destination(case)
    step_id = build_step_id(issue_id=turn.issue_id, turn_index=TURN)
    result, replayed, operation_record_present = await _load_cached_result(
        case,
        turn=turn,
        destination=destination,
        fixture_context=fixture_context,
        protocol_enabled=protocol_enabled,
        step_id=step_id,
    )
    result = case.executor.middleware.apply_after_tool(
        "write_file",
        turn.tool_calls[0].args,
        result,
        replayed=replayed,
        issue=case.issue,
        role_name=turn.role,
        context=fixture_context,
    )
    turn.tool_calls[0].result = result
    result_ref = await _persist_result(
        case,
        destination=destination,
        fixture_context=fixture_context,
        protocol_enabled=protocol_enabled,
        step_id=step_id,
        result=result,
        replayed=replayed,
        operation_record_present=operation_record_present,
    )
    if result_ref is None:
        raise AssertionError("governed legacy leaf publication did not return result authority")
    await finalize_execution_if_needed(
        control_plane_enabled=True,
        control_plane_service=case.service,
        control_plane_run_id=RUN_ID,
        control_plane_attempt_id=ATTEMPT_ID,
        authoritative_result_ref=result_ref,
        violation_reasons=[],
        executed_step_count=1,
    )


async def _load_cached_result(
    case: Any,
    *,
    turn: ExecutionTurn,
    destination: Any,
    fixture_context: dict[str, Any],
    protocol_enabled: bool,
    step_id: str,
) -> tuple[dict[str, Any], bool, bool]:
    run = await case.service.execution_repository.get_run_record(run_id=RUN_ID)
    if run is None or run.current_attempt_id != ATTEMPT_ID:
        raise AssertionError("cached-result leaf fixture requires the seeded current attempt")
    prepare_dispatch = partial(
        prepare_dispatch_if_needed,
        namespace_scope=str(run.namespace_scope or ""),
        control_plane_enabled=True,
        control_plane_service=case.service,
        control_plane_run_id=RUN_ID,
        control_plane_attempt_id=ATTEMPT_ID,
    )
    return await load_or_execute_tool(
        protocol_enabled=protocol_enabled,
        control_plane_enabled=True,
        destination=destination,
        turn=turn,
        tool_name="write_file",
        tool_args=ARGS,
        operation_id=operation_id(),
        binding=None,
        toolbox=case.toolbox,
        context=fixture_context,
        step_id=step_id,
        step_seed=derive_step_seed(run_seed=SESSION, run_id=SESSION, step_id=step_id),
        validator_version=VALIDATOR_VERSION,
        protocol_hash=default_protocol_hash(),
        tool_schema_hash=default_tool_schema_hash(),
        load_operation_result=case.executor.artifact_writer.load_operation_result,
        load_replay_tool_result=case.executor.artifact_writer.load_replay_tool_result,
        prepare_dispatch=prepare_dispatch,
    )


async def _persist_result(
    case: Any,
    *,
    destination: Any,
    fixture_context: dict[str, Any],
    protocol_enabled: bool,
    step_id: str,
    result: dict[str, Any],
    replayed: bool,
    operation_record_present: bool,
) -> str | None:
    common = dict(
        destination=destination,
        tool_name="write_file",
        tool_args=ARGS,
        result=result,
        binding=None,
        operation_id=operation_id(),
        replayed=replayed,
        operation_record_present=operation_record_present,
        control_plane_enabled=True,
        control_plane_service=case.service,
        control_plane_run_id=RUN_ID,
        control_plane_attempt_id=ATTEMPT_ID,
    )
    writer = case.executor.artifact_writer
    if not protocol_enabled:
        return await persist_non_protocol_tool_result_if_needed(
            **common,
            persist_tool_result=writer.persist_tool_result,
            persist_operation_result=writer.persist_operation_result,
        )
    return await persist_protocol_operation(
        **common,
        index=0,
        step_id=step_id,
        receipt_seq=1,
        proposal_hash="legacy-leaf-composition",
        validator_version=VALIDATOR_VERSION,
        protocol_hash=default_protocol_hash(),
        tool_schema_hash=default_tool_schema_hash(),
        execution_capsule=build_execution_capsule(fixture_context),
        context=fixture_context,
        persist_operation_result=writer.persist_operation_result,
        append_protocol_receipt=writer.append_protocol_receipt,
        retry_count=0,
    )
