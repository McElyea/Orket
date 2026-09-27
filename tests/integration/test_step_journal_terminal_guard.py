"""Closing controls for resolved step/effect-journal correspondence."""
from __future__ import annotations

import re
from pathlib import Path

import aiosqlite
import pytest

from orket.application.services.turn_tool_checkpoint_authority import TurnToolCheckpointRecoveryError
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.services.turn_tool_recovery_transaction import recover_pre_effect_attempt_atomic
from orket.application.services.turn_tool_step_publication import _step
from orket.core.contracts.turn_tool_dispatch import is_unresolved_tool_dispatch
from orket.core.domain import AttemptState, ResultClass, RunState
from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.operation_binding import (
    ARGS,
    ATTEMPT_ID,
    ISSUE,
    ROLE,
    RUN_ID,
    SESSION,
    TURN,
    _dump,
    make_case,
    operation_id,
    proposal,
)
from tests.helpers.step_journal_opening import (
    logical_state,
    physical_state,
    remove_current_journal,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]
RESULT_REF = f"turn-tool-result:{RUN_ID}:terminal-guard"
VIOLATIONS = ["E_OPERATION_ARTIFACT_INVALID:result_digest_mismatch"]
SECOND_STEP_ID = "step-without-journal"
SECOND_OPERATION_ID = "operation-distinct-from-step"
UNRESOLVED_STEP_ID = "step-unresolved-precedence"
UNRESOLVED_OPERATION_ID = "operation-unresolved-precedence"


def _missing_journal_pattern(step_id: str) -> str:
    return rf"{re.escape(RUN_ID)}.*{re.escape(step_id)}.*effect journal"

async def _guard_state(case) -> dict[str, object]:  # type: ignore[no-untyped-def]
    state = await logical_state(case)
    steps = await case.service.execution_repository.list_step_records(attempt_id=ATTEMPT_ID)
    state["all_steps"] = [_dump(step) for step in steps]
    return state


async def _damage_journal(case, field: str, value: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert len(effects) == 1
    original = effects[0]
    damaged = original.model_copy(update={field: value})
    async with aiosqlite.connect(case.database) as connection:
        changed = await connection.execute(
            "UPDATE effect_journal_entries SET payload_json = ? WHERE journal_entry_id = ? AND run_id = ?",
            (damaged.model_dump_json(), original.journal_entry_id, RUN_ID),
        )
        assert changed.rowcount == 1
        await connection.commit()
    retained = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert len(retained) == 1 and getattr(retained[0], field) == value
    return {"before": _dump(original), "after": _dump(retained[0])}


async def _assert_unchanged_refusal(case, invoke, error_type, step_id):  # type: ignore[no-untyped-def]
    before_logical = await _guard_state(case)
    before_physical = await physical_state(case)
    with pytest.raises(error_type, match=_missing_journal_pattern(step_id)):
        await invoke()
    assert await _guard_state(case) == before_logical
    assert await physical_state(case) == before_physical


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("run_id", "different-run", id="wrong-run"),
        pytest.param("step_id", "different-step", id="wrong-step"),
        pytest.param("attempt_id", f"{RUN_ID}:attempt:0002", id="cross-attempt"),
    ],
)
# Layer: integration. A malformed or cross-attempt journal cannot cover the resolved current step.
async def test_resolved_step_requires_exact_journal_execution_identity(
    tmp_path: Path, field: str, value: str,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    damage = await _damage_journal(case, field, value)
    assert damage["before"][field] != damage["after"][field]

    async def invoke():
        return await case.service.finalize_execution(
            run_id=RUN_ID,
            attempt_id=ATTEMPT_ID,
            authoritative_result_ref=RESULT_REF,
            violation_reasons=VIOLATIONS,
            executed_step_count=1,
        )

    await _assert_unchanged_refusal(case, invoke, TurnToolControlPlaneError, operation_id())


# Layer: integration. Every resolved step needs coverage; one paired step cannot cover another.
async def test_multi_step_attempt_refuses_when_any_resolved_step_lacks_journal(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    second, _call_digest = _step(
        run=seeded.run,
        attempt_id=ATTEMPT_ID,
        step_id=SECOND_STEP_ID,
        tool_name="write_file",
        tool_args={**ARGS, "path": "agent_output/second.txt"},
        binding=None,
        operation_id=SECOND_OPERATION_ID,
        result={"ok": True, "tool": "write_file", "touched_paths": ["agent_output/second.txt"]},
        replayed=False,
    )
    await case.service.execution_repository.save_step_record(record=second)
    assert second.step_id != SECOND_OPERATION_ID

    async def invoke():
        return await case.service.finalize_execution(
            run_id=RUN_ID,
            attempt_id=ATTEMPT_ID,
            authoritative_result_ref=RESULT_REF,
            violation_reasons=[],
            executed_step_count=2,
        )

    await _assert_unchanged_refusal(case, invoke, TurnToolControlPlaneError, SECOND_STEP_ID)


# Layer: integration. A matching journal uses step identity even when operation identity differs.
async def test_matching_journal_supports_distinct_step_and_operation_identity(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    before_physical = await physical_state(case)
    second, effect = await case.service.publish_step_result(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        step_id=SECOND_STEP_ID,
        tool_name="write_file",
        tool_args={**ARGS, "path": "agent_output/controlled-second.txt"},
        result={"ok": True, "tool": "write_file", "touched_paths": []},
        binding=None,
        operation_id=SECOND_OPERATION_ID,
        replayed=False,
    )
    assert second.step_id == effect.step_id == SECOND_STEP_ID
    assert second.step_id != SECOND_OPERATION_ID
    assert effect.run_id == RUN_ID and effect.attempt_id == ATTEMPT_ID
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert len(effects) == 2 and effect in effects

    run, attempt, truth = await case.service.finalize_execution(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        authoritative_result_ref=RESULT_REF,
        violation_reasons=[],
        executed_step_count=2,
    )

    assert run.lifecycle_state is RunState.COMPLETED
    assert attempt.attempt_state is AttemptState.COMPLETED
    assert truth.result_class is ResultClass.SUCCESS
    assert await physical_state(case) == before_physical
    assert case.toolbox.calls == 1


# Layer: integration. Existing unresolved-dispatch refusal precedes orphan correspondence refusal.
async def test_unresolved_dispatch_precedes_resolved_orphan_guard(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    unresolved = await case.service.prepare_dispatch(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        step_id=UNRESOLVED_STEP_ID,
        tool_name="write_file",
        tool_args={**ARGS, "path": "agent_output/unresolved.txt"},
        binding=None,
        operation_id=UNRESOLVED_OPERATION_ID,
    )
    orphan, _call_digest = _step(
        run=seeded.run,
        attempt_id=ATTEMPT_ID,
        step_id=SECOND_STEP_ID,
        tool_name="write_file",
        tool_args={**ARGS, "path": "agent_output/orphan.txt"},
        binding=None,
        operation_id=SECOND_OPERATION_ID,
        result={"ok": True, "tool": "write_file", "touched_paths": []},
        replayed=False,
    )
    await case.service.execution_repository.save_step_record(record=orphan)
    assert is_unresolved_tool_dispatch(unresolved)
    assert not is_unresolved_tool_dispatch(orphan)
    effects = await case.service.publication.repository.list_effect_journal_entries(run_id=RUN_ID)
    assert all(effect.step_id != SECOND_STEP_ID for effect in effects)
    before_logical = await _guard_state(case)
    before_physical = await physical_state(case)

    with pytest.raises(TurnToolControlPlaneError, match="tool dispatch outcome unknown"):
        await case.service.finalize_execution(
            run_id=RUN_ID,
            attempt_id=ATTEMPT_ID,
            authoritative_result_ref=RESULT_REF,
            violation_reasons=VIOLATIONS,
            executed_step_count=3,
        )

    assert await _guard_state(case) == before_logical
    assert await physical_state(case) == before_physical


# Layer: integration. Recovery uses the same transaction-local correspondence guard.
async def test_recovery_refuses_resolved_step_without_current_journal(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    await remove_current_journal(case)

    async def invoke():
        return await recover_pre_effect_attempt_atomic(
            transactions=case.service.transactions,
            publication=case.service.publication,
            run=seeded.run,
            current_attempt=seeded.attempt,
        )

    await _assert_unchanged_refusal(case, invoke, TurnToolCheckpointRecoveryError, operation_id())


# Layer: integration. Terminal truth cannot be reused after its step/journal correspondence is damaged.
async def test_terminal_reuse_revalidates_resolved_step_journal_correspondence(tmp_path: Path) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    await case.service.finalize_execution(
        run_id=RUN_ID,
        attempt_id=ATTEMPT_ID,
        authoritative_result_ref=RESULT_REF,
        violation_reasons=[],
        executed_step_count=1,
    )
    await remove_current_journal(case)

    async def invoke():
        return await case.service.ensure_reentry_allowed(
            session_id=SESSION,
            issue_id=ISSUE,
            role_name=ROLE,
            turn_index=TURN,
        )

    await _assert_unchanged_refusal(case, invoke, TurnToolControlPlaneError, operation_id())
