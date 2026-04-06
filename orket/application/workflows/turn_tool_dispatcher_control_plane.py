from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneService


async def publish_preflight_failure_if_needed(
    *,
    control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    proposal_hash: str,
    preflight_violations: list[str],
) -> None:
    if not control_plane_enabled or control_plane_service is None:
        return
    await control_plane_service.publish_preflight_failure(
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        proposal_hash=proposal_hash,
        violation_reasons=preflight_violations,
    )


async def begin_control_plane_execution_if_needed(
    *,
    control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None,
    has_tool_calls: bool,
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    proposal_hash: str,
    resume_mode: bool,
) -> tuple[str | None, str | None]:
    if not control_plane_enabled or control_plane_service is None or not has_tool_calls:
        return None, None
    run, attempt = await control_plane_service.begin_execution(
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        proposal_hash=proposal_hash,
        resume_mode=resume_mode,
    )
    return run.run_id, attempt.attempt_id


async def publish_step_if_needed(
    *,
    control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None,
    control_plane_run_id: str | None,
    control_plane_attempt_id: str | None,
    tool_name: str,
    tool_args: dict[str, Any],
    result: dict[str, Any],
    binding: dict[str, Any] | None,
    operation_id: str,
    replayed: bool,
) -> str | None:
    if (
        not control_plane_enabled
        or control_plane_service is None
        or control_plane_run_id is None
        or control_plane_attempt_id is None
    ):
        return None
    await control_plane_service.publish_step_result(
        run_id=control_plane_run_id,
        attempt_id=control_plane_attempt_id,
        step_id=operation_id,
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
        binding=binding,
        operation_id=operation_id,
        replayed=bool(replayed),
    )
    return f"turn-tool-result:{operation_id}"


async def persist_non_protocol_tool_result_if_needed(
    *,
    persist_tool_result: Callable[..., None],
    persist_operation_result: Callable[..., None],
    session_id: str,
    issue_id: str,
    role_name: str,
    turn_index: int,
    tool_name: str,
    tool_args: dict[str, Any],
    result: dict[str, Any],
    control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None,
    control_plane_run_id: str | None,
    control_plane_attempt_id: str | None,
    binding: dict[str, Any] | None,
    operation_id: str,
    replayed: bool,
) -> str | None:
    if control_plane_enabled:
        await asyncio.to_thread(
            persist_operation_result,
            session_id=session_id,
            issue_id=issue_id,
            role_name=role_name,
            turn_index=turn_index,
            operation_id=operation_id,
            tool_name=tool_name,
            tool_args=tool_args,
            result=result,
        )
    await asyncio.to_thread(
        persist_tool_result,
        session_id=session_id,
        issue_id=issue_id,
        role_name=role_name,
        turn_index=turn_index,
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
    )
    return await publish_step_if_needed(
        control_plane_enabled=control_plane_enabled,
        control_plane_service=control_plane_service,
        control_plane_run_id=control_plane_run_id,
        control_plane_attempt_id=control_plane_attempt_id,
        tool_name=tool_name,
        tool_args=tool_args,
        result=result,
        binding=binding,
        operation_id=operation_id,
        replayed=bool(replayed),
    )


async def finalize_execution_if_needed(
    *,
    control_plane_enabled: bool,
    control_plane_service: TurnToolControlPlaneService | None,
    control_plane_run_id: str | None,
    control_plane_attempt_id: str | None,
    authoritative_result_ref: str,
    violation_reasons: list[str],
    executed_step_count: int,
) -> None:
    if (
        not control_plane_enabled
        or control_plane_service is None
        or control_plane_run_id is None
        or control_plane_attempt_id is None
    ):
        return
    await control_plane_service.finalize_execution(
        run_id=control_plane_run_id,
        attempt_id=control_plane_attempt_id,
        authoritative_result_ref=authoritative_result_ref,
        violation_reasons=violation_reasons,
        executed_step_count=executed_step_count,
    )


__all__ = [
    "begin_control_plane_execution_if_needed",
    "finalize_execution_if_needed",
    "persist_non_protocol_tool_result_if_needed",
    "publish_preflight_failure_if_needed",
    "publish_step_if_needed",
]
