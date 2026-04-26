# Layer: integration

from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.sqlite_connection import current_journal_mode
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.domain import AttemptState, RunState, SideEffectBoundaryClass

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_async_control_plane_execution_repository_persists_run_and_attempt_authority(tmp_path: Path) -> None:
    repository = AsyncControlPlaneExecutionRepository(tmp_path / "control_plane.sqlite3")

    run = await repository.save_run_record(
        record=RunRecord(
            run_id="run-1",
            workload_id="sandbox-workload:fastapi-react-postgres",
            workload_version="docker_sandbox_runtime.v1",
            policy_snapshot_id="sandbox-policy:sb-1",
            policy_digest="sha256:policy-1",
            configuration_snapshot_id="sandbox-config:sb-1",
            configuration_digest="sha256:config-1",
            creation_timestamp="2026-03-24T00:00:00+00:00",
            admission_decision_receipt_ref="sandbox-reservation:sb-1",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id="sandbox-attempt:sb-1:00000001",
        )
    )
    attempt = await repository.save_attempt_record(
        record=AttemptRecord(
            attempt_id="sandbox-attempt:sb-1:00000001",
            run_id="run-1",
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref="sandbox-lifecycle:sb-1:starting:initial",
            start_timestamp="2026-03-24T00:00:00+00:00",
        )
    )
    updated_attempt = await repository.save_attempt_record(
        record=attempt.model_copy(
            update={
                "attempt_state": AttemptState.INTERRUPTED,
                "end_timestamp": "2026-03-24T00:02:00+00:00",
                "side_effect_boundary_class": SideEffectBoundaryClass.POST_EFFECT_OBSERVED,
                "failure_class": "lease_expired",
            }
        )
    )
    step = await repository.save_step_record(
        record=StepRecord(
            step_id="tool-op-1",
            attempt_id="sandbox-attempt:sb-1:00000001",
            step_kind="governed_tool_operation",
            input_ref="turn-tool-call:abc",
            output_ref="turn-tool-result:tool-op-1",
            capability_used=None,
            resources_touched=["tool:write_file"],
            observed_result_classification="tool_succeeded",
            receipt_refs=["turn-tool-operation:tool-op-1"],
            closure_classification="step_completed",
        )
    )

    loaded_run = await repository.get_run_record(run_id="run-1")
    loaded_attempt = await repository.get_attempt_record(attempt_id="sandbox-attempt:sb-1:00000001")
    listed_attempts = await repository.list_attempt_records(run_id="run-1")
    loaded_step = await repository.get_step_record(step_id="tool-op-1")
    listed_steps = await repository.list_step_records(attempt_id="sandbox-attempt:sb-1:00000001")

    assert loaded_run == run
    assert loaded_attempt == updated_attempt
    assert [record.attempt_id for record in listed_attempts] == ["sandbox-attempt:sb-1:00000001"]
    assert loaded_step == step
    assert [record.step_id for record in listed_steps] == ["tool-op-1"]


@pytest.mark.asyncio
async def test_async_control_plane_execution_repository_enables_wal_mode(tmp_path: Path) -> None:
    """Layer: integration. Verifies control-plane execution storage selects WAL mode on the real SQLite file."""
    db_path = tmp_path / "control_plane.sqlite3"
    repository = AsyncControlPlaneExecutionRepository(db_path)

    await repository.save_run_record(
        record=RunRecord(
            run_id="run-wal",
            workload_id="sandbox-workload:test",
            workload_version="docker_sandbox_runtime.v1",
            policy_snapshot_id="sandbox-policy:test",
            policy_digest="sha256:policy",
            configuration_snapshot_id="sandbox-config:test",
            configuration_digest="sha256:config",
            creation_timestamp="2026-04-25T00:00:00+00:00",
            admission_decision_receipt_ref="sandbox-reservation:test",
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id="attempt-wal",
        )
    )

    assert await current_journal_mode(db_path) == "wal"
