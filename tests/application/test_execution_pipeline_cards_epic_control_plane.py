import json
from pathlib import Path

import pytest

from orket.application.services.cards_epic_control_plane_service import CardsEpicControlPlaneService
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_epic_assets(root: Path, epic_id: str) -> None:
    _write_json(
        root / "model" / "core" / "teams" / "standard.json",
        {
            "name": "standard",
            "seats": {
                "lead_architect": {
                    "name": "Lead",
                    "roles": ["lead_architect"],
                }
            },
        },
    )
    _write_json(
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Cards epic control-plane test",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [
                {
                    "id": "ISSUE-1",
                    "summary": "Do work",
                    "seat": "lead_architect",
                    "priority": "High",
                    "depends_on": [],
                }
            ],
        },
    )


# Layer: integration
@pytest.mark.asyncio
async def test_run_epic_publishes_invocation_scoped_control_plane_run_for_incomplete_path(
    test_root,
    workspace,
    db_path,
    monkeypatch,
) -> None:
    _write_epic_assets(test_root, "cards_cp_incomplete")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic(
        "cards_cp_incomplete",
        build_id="build-cards-cp-incomplete",
        session_id="sess-cards-cp-incomplete",
    )

    ledger = await pipeline.run_ledger.get_run("sess-cards-cp-incomplete")
    assert ledger is not None
    run_record = dict(ledger["artifact_json"]["control_plane_run_record"])
    attempt_record = dict(ledger["artifact_json"]["control_plane_attempt_record"])
    step_record = dict(ledger["artifact_json"]["control_plane_step_record"])
    control_plane = dict(ledger["summary_json"]["control_plane"])

    assert run_record["lifecycle_state"] == "waiting_on_observation"
    assert attempt_record["attempt_state"] == "attempt_waiting"
    assert step_record["step_kind"] == "cards_epic_session_start"
    assert control_plane["projection_source"] == "control_plane_records"
    assert control_plane["projection_only"] is True
    assert control_plane["run_id"] == run_record["run_id"]
    assert control_plane["run_state"] == "waiting_on_observation"
    assert control_plane["attempt_id"] == attempt_record["attempt_id"]
    assert control_plane["attempt_state"] == "attempt_waiting"
    assert control_plane["step_id"] == step_record["step_id"]
    assert control_plane["step_kind"] == "cards_epic_session_start"

    run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=run_record["run_id"])
    attempt = await pipeline.orchestrator.control_plane_execution_repository.get_attempt_record(
        attempt_id=attempt_record["attempt_id"]
    )
    step = await pipeline.orchestrator.control_plane_execution_repository.get_step_record(
        step_id=CardsEpicControlPlaneService.start_step_id_for(run_id=run_record["run_id"])
    )
    policy_snapshot = await pipeline.orchestrator.control_plane_repository.get_resolved_policy_snapshot(
        snapshot_id=run_record["policy_snapshot_id"]
    )
    configuration_snapshot = await pipeline.orchestrator.control_plane_repository.get_resolved_configuration_snapshot(
        snapshot_id=run_record["configuration_snapshot_id"]
    )

    assert run is not None
    assert run.lifecycle_state.value == "waiting_on_observation"
    assert attempt is not None
    assert attempt.attempt_state.value == "attempt_waiting"
    assert step is not None
    assert step.resources_touched == ["epic:cards_cp_incomplete", "build:build-cards-cp-incomplete"]
    assert policy_snapshot is not None
    assert policy_snapshot.policy_payload["entry_mode"] == "cards_epic_run"
    assert configuration_snapshot is not None
    assert configuration_snapshot.configuration_payload["session_id"] == "sess-cards-cp-incomplete"


# Layer: integration
@pytest.mark.asyncio
async def test_run_epic_publishes_completed_control_plane_run_for_success_path(
    test_root,
    workspace,
    db_path,
    monkeypatch,
) -> None:
    _write_epic_assets(test_root, "cards_cp_done")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _complete_execute_epic(**_kwargs):
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.DONE)
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _complete_execute_epic)

    await pipeline.run_epic(
        "cards_cp_done",
        build_id="build-cards-cp-done",
        session_id="sess-cards-cp-done",
    )

    ledger = await pipeline.run_ledger.get_run("sess-cards-cp-done")
    assert ledger is not None
    run_record = dict(ledger["artifact_json"]["control_plane_run_record"])
    attempt_record = dict(ledger["artifact_json"]["control_plane_attempt_record"])
    control_plane = dict(ledger["summary_json"]["control_plane"])

    run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=run_record["run_id"])
    attempt = await pipeline.orchestrator.control_plane_execution_repository.get_attempt_record(
        attempt_id=attempt_record["attempt_id"]
    )

    assert run is not None
    assert run.lifecycle_state.value == "completed"
    assert attempt is not None
    assert attempt.attempt_state.value == "attempt_completed"
    assert attempt.end_timestamp is not None
    assert control_plane["run_id"] == run_record["run_id"]
    assert control_plane["run_state"] == "completed"
    assert control_plane["attempt_id"] == attempt_record["attempt_id"]
    assert control_plane["attempt_state"] == "attempt_completed"


# Layer: integration
@pytest.mark.asyncio
async def test_run_epic_same_session_and_build_creates_new_invocation_scoped_control_plane_run(
    test_root,
    workspace,
    db_path,
    monkeypatch,
) -> None:
    _write_epic_assets(test_root, "cards_cp_rerun")
    pipeline = ExecutionPipeline(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
    )

    async def _no_op_execute_epic(**_kwargs):
        return None

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", _no_op_execute_epic)

    await pipeline.run_epic(
        "cards_cp_rerun",
        build_id="build-cards-cp-rerun",
        session_id="sess-cards-cp-rerun",
    )
    first_ledger = await pipeline.run_ledger.get_run("sess-cards-cp-rerun")
    assert first_ledger is not None
    first_run_id = str(first_ledger["artifact_json"]["control_plane_run_record"]["run_id"])

    await pipeline.run_epic(
        "cards_cp_rerun",
        build_id="build-cards-cp-rerun",
        session_id="sess-cards-cp-rerun",
    )
    second_ledger = await pipeline.run_ledger.get_run("sess-cards-cp-rerun")
    assert second_ledger is not None
    second_run_id = str(second_ledger["artifact_json"]["control_plane_run_record"]["run_id"])

    first_run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=first_run_id)
    second_run = await pipeline.orchestrator.control_plane_execution_repository.get_run_record(run_id=second_run_id)

    assert first_run_id != second_run_id
    assert first_run is not None
    assert first_run.lifecycle_state.value == "waiting_on_observation"
    assert second_run is not None
    assert second_run.lifecycle_state.value == "waiting_on_observation"
