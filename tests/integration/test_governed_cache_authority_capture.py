"""Integration controls for governed cache authority captured around native reads."""
from __future__ import annotations

import json
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from orket.application.workflows.turn_artifact_writer import OperationRecordValidationError
from orket.application.workflows.turn_executor import ToolValidationError
from orket.core.domain.control_plane_final_truth import ControlPlaneFinalTruthError
from orket.core.domain.execution import ToolCallErrorClass
from tests.helpers.governed_cache_authority import (
    authority_state,
    close_seeded_run,
    mutate_authority,
    physical_call_files,
    release_and_join,
    run_dispatch,
    start_held_dispatch,
    wait_for_hold,
)
from tests.helpers.governed_operation_binding import seed_open_cache
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.operation_binding import (
    artifact_paths,
    captured_destination,
    make_case,
    operation_id,
    proposal,
)
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
    pytest.mark.usefixtures("deterministic_turn_clock"),
]


def _record(record_property, name: str, observation: SimpleNamespace) -> None:  # type: ignore[no-untyped-def]
    outcome = observation.outcome
    record_property(
        name,
        json.dumps(
            {
                "admission_state": observation.admission_state,
                "mutation": observation.mutation,
                "mutated_state": observation.mutated_state,
                "after_state": observation.after_state,
                "mutated_files": observation.mutated_files,
                "after_files": observation.after_files,
                "call_error": observation.turn.tool_calls[0].error,
                "route_error": str(outcome) if isinstance(outcome, BaseException) else None,
                "native_finished": observation.admitted.hold.finished.is_set(),
                "watchdog_expired": observation.admitted.hold.expired,
            },
            sort_keys=True,
        ),
    )


async def _held_observation(
    tmp_path: Path,
    monkeypatch,
    record_property,
    selected_clock,
    mutation: str | None,
) -> SimpleNamespace:  # type: ignore[no-untyped-def]
    case = make_case(tmp_path, [proposal()])
    seeded = await seed_open_cache(case, anchor="coherent")
    if mutation == "final_truth_corrupt":
        await close_seeded_run(case)
    target = (await artifact_paths(case))["operation"]
    admitted = start_held_dispatch(case, monkeypatch, target)
    try:
        await wait_for_hold(admitted)
        admission_state = await authority_state(case)
        admission_files = await physical_call_files(case, target)
        namespace_timestamp = (
            selected_clock() if mutation == "namespace_mismatch" else None
        )
        mutation_detail = (
            {} if mutation is None else await mutate_authority(
                case, seeded, mutation,
                namespace_publication_timestamp=namespace_timestamp,
            )
        )
        mutated_state = await authority_state(case)
        mutated_files = await physical_call_files(case, target)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        assert not admitted.hold.expired and not admitted.task.done()
    finally:
        outcome = await release_and_join(admitted)
    return SimpleNamespace(
        admitted=admitted,
        admission_files=admission_files,
        admission_state=admission_state,
        after_files=await physical_call_files(case, target),
        after_state=await authority_state(case),
        case=case,
        mutation=mutation_detail,
        mutated_files=mutated_files,
        mutated_state=mutated_state,
        outcome=outcome,
        seeded=seeded,
        turn=admitted.turn,
    )


# Layer: integration
async def test_governed_cache_healthy_authority_survives_held_operation_read(
    tmp_path: Path,
    monkeypatch,
    record_property,
    deterministic_turn_clock,
) -> None:
    observed = await _held_observation(
        tmp_path, monkeypatch, record_property, deterministic_turn_clock, None,
    )
    _record(record_property, "governed_cache_authority_healthy", observed)
    call = observed.turn.tool_calls[0]

    assert not isinstance(observed.outcome, BaseException)
    assert call.result == observed.seeded.result and call.error is None
    assert observed.case.toolbox.calls == 1 and len(observed.case.probe.calls) == 1
    assert observed.after_state["steps"] == observed.mutated_state["steps"]
    assert observed.after_state["effects"] == observed.mutated_state["effects"]
    assert observed.after_files["operation"] == observed.mutated_files["operation"]
    assert observed.after_files["effect"] == observed.mutated_files["effect"]
    assert observed.admission_files["receipt"] is None
    assert observed.after_files["receipt"] is not None


@pytest.mark.parametrize(
    ("mutation", "detail"),
    [
        pytest.param("configuration_absent", "dispatch contract missing", id="configuration-absent"),
        pytest.param("unresolved_sibling", "tool dispatch outcome unknown", id="unresolved-sibling"),
        pytest.param("lease_revoked", "non-active lease", id="revoked-lease"),
        pytest.param("resource_mismatch", "resource namespace scope drift", id="resource-mismatch"),
        pytest.param("namespace_mismatch", "run namespace changed", id="run-namespace-mismatch"),
        pytest.param("current_attempt_advanced", "requires the current governed attempt", id="attempt-advanced"),
        pytest.param(
            "final_truth_corrupt",
            "E_CONTROL_PLANE_TERMINAL_AUTHORITY_CONFLICT:result",
            id="final-truth-domain-error",
        ),
    ],
)
# Layer: integration
async def test_governed_cache_refuses_authority_changed_during_held_operation_read(
    tmp_path: Path,
    monkeypatch,
    record_property,
    deterministic_turn_clock,
    mutation: str,
    detail: str,
) -> None:
    observed = await _held_observation(
        tmp_path, monkeypatch, record_property, deterministic_turn_clock, mutation,
    )
    _record(record_property, f"governed_cache_authority_{mutation}", observed)
    call = observed.turn.tool_calls[0]

    assert isinstance(
        observed.outcome,
        (ToolValidationError, TurnToolControlPlaneError, ControlPlaneFinalTruthError),
    )
    assert call.result is None
    assert call.error_class is ToolCallErrorClass.EXECUTION_FAILED
    assert "E_OPERATION_ARTIFACT_INVALID:control_plane_anchor_mismatch" in str(call.error)
    assert detail in str(call.error)
    assert observed.case.toolbox.calls == 1 and observed.case.probe.calls == []
    assert observed.after_state["steps"] == observed.mutated_state["steps"]
    assert observed.after_state["effects"] == observed.mutated_state["effects"]
    for name in ("operation", "receipt", "effect"):
        assert observed.after_files[name] == observed.mutated_files[name]


# Layer: integration
async def test_operation_reader_refuses_operations_directory_file_as_malformed(
    tmp_path: Path,
    record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    destination = await captured_destination(case)
    operations = destination.output_dir / "operations"
    relative = operations.relative_to(case.workspace).as_posix()
    files = AsyncFileTools(case.workspace)
    await files.write_file(relative, "directory-blocker")

    with pytest.raises(OperationRecordValidationError) as raised:
        await run_owned_thread(
            partial(
                case.executor.artifact_writer.load_operation_result,
                destination=destination,
                operation_id=operation_id(),
            ),
            label="test-operation-directory-file",
        )
    physical = await files.read_file(relative)
    record_property(
        "operation_directory_file_observation",
        json.dumps({"error": str(raised.value), "physical": physical}, sort_keys=True),
    )

    assert raised.value.reason == "malformed"
    assert "operation record path is unreadable" in str(raised.value)
    assert physical == "directory-blocker"
    assert case.toolbox.calls == 0 and case.probe.calls == []


# Layer: integration
async def test_composed_governed_cache_refuses_operations_directory_file_without_redispatch(
    tmp_path: Path,
    record_property,
) -> None:
    case = make_case(tmp_path, [proposal()])
    await seed_open_cache(case, anchor="coherent")
    operation = (await artifact_paths(case))["operation"]
    await run_owned_thread(operation.unlink, label="test-operation-remove")
    await run_owned_thread(operation.parent.rmdir, label="test-operation-directory-remove")
    blocker = operation.parent
    relative = blocker.relative_to(case.workspace).as_posix()
    files = AsyncFileTools(case.workspace)
    await files.write_file(relative, "directory-blocker")
    before_state = await authority_state(case)
    before_files = await physical_call_files(case, blocker)

    turn, outcome = await run_dispatch(case)
    after_state = await authority_state(case)
    after_files = await physical_call_files(case, blocker)
    call = turn.tool_calls[0]
    record_property(
        "composed_operation_directory_file_observation",
        json.dumps(
            {
                "error": call.error,
                "route_error": str(outcome),
                "before_state": before_state,
                "after_state": after_state,
                "before_files": before_files,
                "after_files": after_files,
            },
            sort_keys=True,
        ),
    )

    assert isinstance(outcome, ToolValidationError)
    assert call.result is None and call.error_class is ToolCallErrorClass.EXECUTION_FAILED
    assert "E_OPERATION_ARTIFACT_INVALID:malformed" in str(call.error)
    assert "operation record path is unreadable" in str(call.error)
    assert case.toolbox.calls == 1 and case.probe.calls == []
    assert after_state["steps"] == before_state["steps"]
    assert after_state["effects"] == before_state["effects"]
    assert after_files == before_files
    assert await files.read_file(relative) == "directory-blocker"
