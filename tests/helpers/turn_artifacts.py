"""Explicit artifact/clock inputs for migrated standalone workflow fixtures."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_control_plane_binding import capture_turn_control_plane_binding
from orket.application.workflows.turn_memory_trace_artifacts import capture_memory_trace_inputs


def artifact_test_utc_now():
    return datetime.now(UTC)


def artifact_destination(writer, *, session_id, issue_id, role_name, turn_index, role_id=None):
    workspace, = capture_file_roots([writer.workspace])
    return TurnArtifactDestination(writer=writer, workspace=workspace, session_id=session_id,
        issue_id=issue_id, role_name=role_name, role_id=role_id, turn_index=turn_index)


def executor_destination(executor, issue, role, context):
    return artifact_destination(executor.artifact_writer,
        session_id=str(context.get("session_id", "unknown-session")), issue_id=issue.id,
        role_name=str(role.name or "").strip(), role_id=str(role.id), turn_index=int(context.get("turn_index", 0)))


def _rewrite_checkpoint_plan_operation(executor, issue, role, context, tool_args):
    destination = executor_destination(executor, issue, role, context)
    snapshot_path = sorted(destination.output_dir.glob("control_plane_checkpoint_snapshot_*.json"))[0]
    snapshot_before = snapshot_path.read_bytes()
    operation_path = sorted((destination.output_dir / "operations").glob("*.json"))[0]
    operation_record = json.loads(operation_path.read_text(encoding="utf-8"))
    executor.artifact_writer.persist_operation_result(
        destination=destination,
        operation_id=str(operation_record["operation_id"]),
        tool_name=str(operation_record["tool"]),
        tool_args=tool_args,
        result=dict(operation_record["result"]),
    )
    return snapshot_path, snapshot_before


async def rewrite_checkpoint_plan_operation_fixture(executor, issue, role, context, tool_args):
    captured_args = dict(tool_args)
    return await asyncio.to_thread(
        _rewrite_checkpoint_plan_operation,
        executor, issue, role, context, captured_args,
    )


async def read_artifact_bytes(path: Path) -> bytes:
    return await asyncio.to_thread(path.read_bytes)


def message_destination(builder, issue, role, context):
    # A standalone MessageBuilder fixture has no executor/writer owner to share.
    return artifact_destination(TurnArtifactWriter(builder.workspace),
        session_id=str(context.get("session_id", "unknown-session")), issue_id=issue.id,
        role_name=str(role.name or "").strip(), role_id=str(role.id), turn_index=int(context.get("turn_index", 0)))


def dispatch_destination(writer, turn, context):
    return artifact_destination(writer, session_id=str(context.get("session_id", "unknown-session")),
        issue_id=turn.issue_id, role_name=turn.role, turn_index=int(context.get("turn_index", 0)))


async def prepare_message_fixture(builder, *, issue, role, context, system_prompt=None):
    destination = message_destination(builder, issue, role, context)
    return await builder.prepare_messages(issue=issue, role=role, context=context,
                                          system_prompt=system_prompt, destination=destination)


async def prepare_executor_message_fixture(executor, issue, role, context, system_prompt=None):
    destination = executor_destination(executor, issue, role, context)
    return await executor._prepare_messages(issue, role, context, system_prompt, destination=destination)


async def execute_dispatch_fixture(dispatcher, *, writer, turn, toolbox, context, issue=None, on_turn_captured=None):
    return await dispatcher.execute_tools(
        destination=dispatch_destination(writer, turn, context),
        control_plane=capture_turn_control_plane_binding(dispatcher=dispatcher, issue_id=turn.issue_id, context=context),
        memory_inputs=capture_memory_trace_inputs(context), memory_events=context.get("_memory_trace_events"),
        turn=turn, toolbox=toolbox, context=context, issue=issue, on_turn_captured=on_turn_captured,
    )


async def execute_executor_dispatch_fixture(executor, **kwargs):
    return await execute_dispatch_fixture(executor.tool_dispatcher, writer=executor.artifact_writer, **kwargs)


async def write_checkpoint_fixture(*, executor, turn, context, prompt_hash):
    from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor, turn=turn, context=context, prompt_hash=prompt_hash,
        control_plane=capture_turn_control_plane_binding(
            dispatcher=executor.tool_dispatcher, issue_id=turn.issue_id, context=context),
        destination=dispatch_destination(executor.artifact_writer, turn, context),
    )
