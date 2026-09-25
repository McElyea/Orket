"""Open-run fixtures for governed operation-cache anchors."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from orket.application.services.turn_tool_control_plane_support import (
    effect_id_for,
    tool_authorization_ref,
    tool_operation_ref,
    tool_result_ref,
    utc_now,
)
from orket.application.services.turn_tool_step_publication import _step
from orket.core.contracts import AttemptRecord
from orket.core.domain import ResidualUncertaintyClassification
from tests.helpers.operation_binding import (
    ARGS,
    ISSUE,
    ROLE,
    RUN_ID,
    SESSION,
    TURN,
    captured_destination,
    context,
    operation_id,
)

__test__ = False


async def _persist_seed_operation(case, stored_args, result) -> None:  # type: ignore[no-untyped-def]
    selected = await captured_destination(case)
    await asyncio.to_thread(
        case.executor.artifact_writer.persist_operation_result,
        destination=selected,
        operation_id=operation_id(),
        tool_name="write_file",
        tool_args=stored_args,
        result=result,
    )


async def _publish_other_attempt_anchor(
    case, run, attempt, stored_args, result,
) -> None:  # type: ignore[no-untyped-def]
    other_id = f"{RUN_ID}:attempt:0002"
    other_fields = attempt.model_dump(mode="json", exclude={"state_revision"})
    other = AttemptRecord.model_validate({
        **other_fields, "attempt_id": other_id, "attempt_ordinal": 2,
    })
    await case.service.execution_repository.save_attempt_record(record=other)
    step, call_digest = _step(
        run=run,
        attempt_id=other_id,
        step_id=operation_id(),
        tool_name="write_file",
        tool_args=stored_args,
        binding=None,
        operation_id=operation_id(),
        result=result,
        replayed=False,
    )
    await case.service.execution_repository.save_step_record(record=step)
    await case.service.publication.append_effect_journal_entry(
        journal_entry_id=f"turn-tool-journal:{operation_id()}",
        effect_id=effect_id_for(operation_id=operation_id()),
        run_id=RUN_ID,
        attempt_id=other_id,
        step_id=operation_id(),
        authorization_basis_ref=tool_authorization_ref(tool_call_digest=call_digest),
        publication_timestamp=utc_now(),
        intended_target_ref=step.resources_touched[0],
        observed_result_ref=tool_result_ref(operation_id=operation_id()),
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref=tool_operation_ref(operation_id=operation_id()),
    )


async def seed_open_cache(
    case,
    *,
    anchor: str,
    stored_args: dict[str, Any] | None = None,
    persist: bool = True,
    execute_effect: bool = True,
) -> SimpleNamespace:  # type: ignore[no-untyped-def]
    selected_args = dict(ARGS if stored_args is None else stored_args)
    run, attempt = await case.service.begin_execution(
        session_id=SESSION,
        issue_id=ISSUE,
        role_name=ROLE,
        turn_index=TURN,
        proposal_hash="seed-proposal",
    )
    result = {"ok": True, "tool": "write_file", "touched_paths": [selected_args["path"]]}
    if execute_effect:
        result = await case.toolbox.execute("write_file", selected_args, context())
    if persist:
        await _persist_seed_operation(case, selected_args, result)
    if anchor in {"coherent", "mismatch"}:
        anchor_args = selected_args if anchor == "coherent" else {**selected_args, "content": "anchor-b"}
        await case.service.publish_step_result(
            run_id=run.run_id, attempt_id=attempt.attempt_id, step_id=operation_id(),
            tool_name="write_file", tool_args=anchor_args, result=result, binding=None,
            operation_id=operation_id(), replayed=False,
        )
    elif anchor == "other_attempt":
        await _publish_other_attempt_anchor(case, run, attempt, selected_args, result)
    elif anchor != "absent":
        raise AssertionError(f"unknown anchor shape: {anchor}")
    return SimpleNamespace(run=run, attempt=attempt, result=result, args=selected_args)
