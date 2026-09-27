"""A resolved governed step cannot authorize terminal truth without its effect journal."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.operation_binding import ATTEMPT_ID, RUN_ID, make_case, proposal
from tests.helpers.step_journal_opening import (
    observe_terminal,
    remove_current_journal,
    remove_current_step,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]
RESULT_REF = f"turn-tool-violations:{RUN_ID}"
VIOLATIONS = ["E_OPERATION_ARTIFACT_INVALID:result_digest_mismatch"]
COUNTS = [
    pytest.param(0, id="count-zero"),
    pytest.param(1, id="count-positive"),
    pytest.param(None, id="count-inferred"),
]
OUTCOMES = [
    pytest.param([], id="success"),
    pytest.param(VIOLATIONS, id="failure"),
]


def _record(record_property, name: str, observation: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    record_property(name, json.dumps(observation, sort_keys=True))


def _current_attempt(state: dict[str, object]) -> dict[str, object]:
    attempts = state["attempts"]
    assert isinstance(attempts, list)
    return next(row for row in attempts if row["attempt_id"] == ATTEMPT_ID)


@pytest.mark.parametrize("executed_step_count", COUNTS)
@pytest.mark.parametrize("violation_reasons", OUTCOMES)
# Layer: integration. Real SQLite, physical tool effect, and atomic terminal publication.
async def test_orphaned_resolved_step_refuses_every_terminal_publication(
    tmp_path: Path,
    record_property,
    executed_step_count: int | None,
    violation_reasons: list[str],
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    removed = await remove_current_journal(case)
    observation = await observe_terminal(
        case,
        executed_step_count=executed_step_count,
        violation_reasons=violation_reasons,
        authoritative_result_ref=RESULT_REF,
    )
    observation["removed_journal"] = removed
    _record(record_property, "step_journal_terminal_observation", observation)

    before = observation["before_logical"]
    assert before["step"]["attempt_id"] == ATTEMPT_ID
    assert before["step"]["output_ref"] is not None
    assert before["effects"] == [] and before["truth"] is None and before["decision"] is None
    assert observation["before_physical"]["effect"]["utf8"] == "effect-a"
    assert observation["before_physical"]["toolbox_calls"] == 1
    assert observation["outcome"]["kind"] == "error", observation
    assert observation["outcome"]["type"] == "TurnToolControlPlaneError"
    assert observation["after_logical"] == before
    assert observation["after_physical"] == observation["before_physical"]


# Layer: integration. A real retained journal remains post-effect authority without its paired step.
async def test_journal_only_control_retains_post_effect_failure(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    removed = await remove_current_step(case)
    observation = await observe_terminal(
        case,
        executed_step_count=0,
        violation_reasons=VIOLATIONS,
        authoritative_result_ref=RESULT_REF,
    )
    observation["removed_step"] = removed
    _record(record_property, "step_journal_control_observation", observation)

    before, after = observation["before_logical"], observation["after_logical"]
    assert before["step"] is None and len(before["effects"]) == 1
    effect = before["effects"][0]
    assert effect["attempt_id"] == ATTEMPT_ID
    assert effect["step_id"] == removed["step_id"]
    assert effect["journal_entry_id"] == f"turn-tool-journal:{removed['step_id']}"
    assert observation["outcome"]["kind"] == "returned"
    assert _current_attempt(after)["side_effect_boundary_class"] == "post_effect_observed"
    assert after["truth"]["result_class"] == "failed"
    assert after["effects"] == before["effects"]
    assert observation["after_physical"] == observation["before_physical"]


# Layer: integration. Evidence from another attempt cannot classify the current attempt post-effect.
async def test_other_attempt_effect_does_not_upgrade_current_attempt(
    tmp_path: Path, record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="other_attempt")
    observation = await observe_terminal(
        case,
        executed_step_count=0,
        violation_reasons=VIOLATIONS,
        authoritative_result_ref=RESULT_REF,
    )
    _record(record_property, "step_journal_control_observation", observation)

    before, after = observation["before_logical"], observation["after_logical"]
    assert before["step"] is not None and before["step"]["attempt_id"] != ATTEMPT_ID
    assert len(before["effects"]) == 1
    effect = before["effects"][0]
    assert effect["attempt_id"] == before["step"]["attempt_id"]
    assert effect["step_id"] == before["step"]["step_id"]
    assert observation["outcome"]["kind"] == "returned"
    assert _current_attempt(after)["side_effect_boundary_class"] == "pre_effect_failure"
    assert after["truth"]["result_class"] == "blocked"
    assert after["effects"] == before["effects"]
    assert observation["after_physical"] == observation["before_physical"]
