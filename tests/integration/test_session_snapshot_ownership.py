"""Layer: integration. Session snapshots retain selected clocks and destinations.

Publication collaborators outside the real snapshot and journal stores are bounded stand-ins.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.runtime.execution_pipeline import ExecutionPipeline
from orket.schema import EpicConfig, TeamConfig
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.helpers.session_snapshot_ownership import (
    STAMP,
    RecordingClock,
    decoded_config,
    historical_plan,
    physical_file,
    publication_journal_observation,
    publication_service,
    publication_state,
    run_publication_case,
    run_repository_path_case,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _PoisonSnapshots:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, _session_id: str) -> None:
        self.calls.append("get")
        raise AssertionError("snapshot=None publication must not read snapshots")

    async def record(self, _session_id: str, _config, _logs) -> None:
        self.calls.append("record")
        raise AssertionError("snapshot=None publication must not write snapshots")


# Layer: integration
async def test_session_checkpoint_payload_uses_selected_turn_clock(
    test_root: Path, workspace: Path, db_path: str, record_property,
) -> None:
    await asyncio.to_thread(_write_epic_assets, test_root, "snapshot_clock")
    clock = RecordingClock()
    operations = ["assets_written"]
    async with ExecutionPipeline.open(
        workspace=workspace,
        department="core",
        db_path=db_path,
        config_root=test_root,
        runtime_inputs=clock,
    ) as pipeline:
        epic = await pipeline.loader.load_asset_async("epics", "snapshot_clock", EpicConfig)
        team = await pipeline.loader.load_asset_async("teams", "standard", TeamConfig)
        environment = await pipeline.loader.load_environment_asset_async("standard")
        before_clock = list(clock.observations)
        before_row = await pipeline.snapshots.get("clock-session")
        before_physical = await physical_file(Path(pipeline.snapshots.db_path))
        await pipeline.orchestrator._save_checkpoint(
            "clock-session", epic, team, environment, "clock-build"
        )
        operations.append("checkpoint_returned")
        row = await pipeline.snapshots.get("clock-session")
        after_clock = list(clock.observations)
        observation = {
            "clock": {"before": before_clock, "after": after_clock,
                      "delta": after_clock[len(before_clock):]},
            "before_row": before_row,
            "row": row,
            "config": decoded_config(row),
            "physical": {"before": before_physical,
                         "after": await physical_file(Path(pipeline.snapshots.db_path))},
            "operations": operations,
        }
        record_property("session_snapshot_clock_observation", json.dumps(observation, sort_keys=True))
        assert before_row is None
        assert row is not None
        assert observation["config"]["timestamp"] == STAMP
        assert observation["clock"]["delta"] == [STAMP]
        assert str(row["captured_at"]).strip()


@pytest.mark.parametrize("mutate", [False, True], ids=["unchanged", "path-a-to-b"])
# Layer: integration
async def test_snapshot_repository_binds_path_before_owned_lock_wait(
    tmp_path: Path, record_property, mutate: bool,
) -> None:
    observation = await run_repository_path_case(
        tmp_path / "repository-case", mutate=mutate, record_property=record_property
    )
    record_property("snapshot_path_observation", json.dumps(observation, sort_keys=True))
    before, after = observation["before"], observation["after"]
    assert observation["cleanup"] == {"task_done": True, "drained": True}
    assert observation["hold"] == {"active_before_responsive_probe": True, "watchdog_expired": False}
    assert before["a_row"] is None and before["b_row"] is None
    assert before["physical"]["a"]["exists"] and before["physical"]["b"]["exists"]
    assert after["physical"]["a"]["exists"] and after["physical"]["b"]["exists"]
    assert decoded_config(after["a_row"]) == {"value": "captured-a"}
    assert after["b_row"] is None
    assert before["seed_rows"]["b"] == after["seed_rows"]["b"]
    assert before["physical"]["b"] == after["physical"]["b"]


# Layer: integration
async def test_snapshot_repository_captures_borrowed_inputs_before_owned_lock_wait(
    tmp_path: Path, record_property,
) -> None:
    observation = await run_repository_path_case(
        tmp_path / "repository-input-case", mutate=False, mutate_inputs=True,
        record_property=record_property,
    )
    record_property("snapshot_input_observation", json.dumps(observation, sort_keys=True))
    before, after = observation["before"], observation["after"]
    persisted = {"config": decoded_config(after["a_row"]),
                 "logs": json.loads(after["a_row"]["log_history"])}
    assert observation["cleanup"] == {"task_done": True, "drained": True}
    assert observation["hold"] == {"active_before_responsive_probe": True, "watchdog_expired": False}
    assert observation["borrowed"]["before"] != observation["borrowed"]["after"]
    assert persisted == observation["borrowed"]["before"]
    assert before["a_row"] is None and before["b_row"] is None
    assert after["b_row"] is None
    assert before["seed_rows"]["b"] == after["seed_rows"]["b"]
    assert before["physical"]["b"] == after["physical"]["b"]


@pytest.mark.parametrize("route", ["publish", "recover"])
@pytest.mark.parametrize("mutate", [False, True], ids=["unchanged", "publisher-a-to-b"])
# Layer: integration
async def test_epic_publication_binds_snapshot_publisher_before_journal_wait(
    tmp_path: Path, record_property, route: str, mutate: bool,
) -> None:
    observation = await run_publication_case(
        tmp_path / f"{route}-{mutate}", route=route, mutate=mutate,
        record_property=record_property,
    )
    record_property("snapshot_publication_observation", json.dumps(observation, sort_keys=True))
    before, after = observation["before"], observation["after"]
    journal_before = observation["journal"]["before"]
    assert observation["cleanup"] == {"task_done": True, "drained": True}
    assert observation["hold"] == {"active_before_responsive_probe": True, "watchdog_expired": False}
    assert before["b_row"] is None
    if route == "publish":
        assert before["a_row"] is None
        assert not journal_before["physical"]["exists"]
    else:
        assert decoded_config(before["a_row"]) == observation["expected_snapshot"]
        assert "timestamp" not in decoded_config(before["a_row"])
        assert journal_before["phase"] == 4
        assert not journal_before["outcome_present"]
    assert observation["error"] is None
    assert observation["result"]["observation"] == "published"
    assert decoded_config(after["a_row"]) == observation["expected_snapshot"]
    assert "timestamp" not in decoded_config(after["a_row"])
    assert after["b_row"] is None
    assert before["seed_rows"]["b"] == after["seed_rows"]["b"]
    assert before["physical"]["b"] == after["physical"]["b"]
    assert observation["journal"]["after"]["physical"]["exists"]
    assert observation["journal"]["after"]["phase"] == 4
    assert not observation["journal"]["after"]["outcome_present"]


# Layer: integration
async def test_epic_publication_preserves_snapshotless_incomplete_plan(
    tmp_path: Path, record_property,
) -> None:
    root = tmp_path / "snapshotless-publication"
    await asyncio.to_thread(root.mkdir, parents=True, exist_ok=True)
    plan = historical_plan("snapshotless-session").model_copy(update={"snapshot": None})
    state = publication_state(plan)
    snapshots = _PoisonSnapshots()
    journal = SQLiteEpicPublicationRepository(root / "publication.db")
    published = await publication_service(journal, snapshots, state, root).publish(plan)
    after_publish = await publication_journal_observation(journal, plan.session_id)
    reopened = SQLiteEpicPublicationRepository(root / "publication.db")
    recovered = await publication_service(reopened, snapshots, state, root).recover(
        plan.session_id, plan.request
    )
    observation = {
        "plan_snapshot": plan.snapshot,
        "retained_status": state.ledger.row["status"],
        "snapshot_calls": list(snapshots.calls),
        "published": published.model_dump(mode="json"),
        "recovered": None if recovered is None else recovered.model_dump(mode="json"),
        "journal": {"after_publish": after_publish,
                    "after_recover": await publication_journal_observation(reopened, plan.session_id)},
    }
    record_property("snapshotless_publication_observation", json.dumps(observation, sort_keys=True))
    assert observation["plan_snapshot"] is None
    assert observation["retained_status"] == "incomplete"
    assert observation["snapshot_calls"] == []
    assert observation["published"]["observation"] == "published"
    assert observation["recovered"]["observation"] == "published"
    assert observation["published"]["run"]["lifecycle_state"] == "waiting_on_observation"
    assert observation["recovered"]["run"]["lifecycle_state"] == "waiting_on_observation"
    assert observation["journal"]["after_publish"]["phase"] == 4
    assert observation["journal"]["after_recover"]["phase"] == 4
    assert observation["journal"]["after_publish"]["physical"]["exists"]
    assert observation["journal"]["after_recover"]["physical"]["exists"]
    assert (observation["journal"]["after_publish"]["physical"]["path"]
            == observation["journal"]["after_recover"]["physical"]["path"])
    assert not observation["journal"]["after_publish"]["outcome_present"]
    assert not observation["journal"]["after_recover"]["outcome_present"]
