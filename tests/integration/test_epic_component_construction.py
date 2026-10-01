"""Real pipeline composition and SQLite; constructor faults are supplied controls."""
from __future__ import annotations

from pathlib import Path

import pytest

from orket.runtime.execution import execution_pipeline as pipeline_module
from tests.integration.test_execution_policy_input_capture import pipeline_at
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def observe_construction(monkeypatch, *, failure_stage=None):
    observed = {"order": [], "instances": {}, "failure": OSError("composition-fault")}
    calendar = pipeline_module.EosSprintBaseline.from_environment
    owner_type = pipeline_module.EpicRunOrchestrator

    def unexpected_owner_lookup(*args, **kwargs):
        raise AssertionError("Owner constructor lookup moved after calendar observation")

    def read_calendar(environment):
        result = calendar(environment)
        observed["order"].append("calendar")
        monkeypatch.setattr(pipeline_module, "EpicRunOrchestrator", unexpected_owner_lookup)
        return result

    def observe_initializer(owner, label):
        initialize = owner.__init__

        def initialize_and_observe(instance, *args, **kwargs):
            initialize(instance, *args, **kwargs)
            observed["order"].append(label)
            observed["instances"][label] = instance
            if failure_stage == label:
                raise observed["failure"]

        monkeypatch.setattr(owner, "__init__", initialize_and_observe)

    monkeypatch.setattr(pipeline_module.EosSprintBaseline, "from_environment", read_calendar)
    observe_initializer(pipeline_module.EpicApprovalPauseService, "pauses")
    observe_initializer(pipeline_module.EpicPreparationService, "preparation")
    observe_initializer(pipeline_module.EpicRunCallbacks, "callbacks")
    observe_initializer(owner_type, "owner")
    request_for = pipeline_module.EpicApprovalPauseService.request_for

    async def observe_request(instance, *args, **kwargs):
        observed["order"].append("request")
        observed["instances"]["request"] = instance
        return await request_for(instance, *args, **kwargs)

    monkeypatch.setattr(pipeline_module.EpicApprovalPauseService, "request_for", observe_request)
    return observed


async def retained_state(pipeline):
    paths = {Path(pipeline.db_path), Path(pipeline.cards_epic_control_plane.execution_repository.db_path)}
    return {str(path): await logical_state(path) for path in paths}


@pytest.mark.parametrize("surface", ["dispatch", "resume"])
@pytest.mark.parametrize("stage", ["pauses", "preparation", "owner"])
async def test_constructor_failure_precedes_dispatch_or_pause_lookup(tmp_path, monkeypatch, surface, stage):
    """Layer: integration. Exact constructor failure leaves real retained state unchanged."""
    pipeline = await pipeline_at(tmp_path)
    try:
        before = await retained_state(pipeline)
        observed = observe_construction(monkeypatch, failure_stage=stage)
        with pytest.raises(OSError) as caught:
            if surface == "dispatch":
                await pipeline.run_card("publication_epic", session_id="composition", build_id="composition")
            else:
                await pipeline.resume_epic_approval(session_id="composition", approval_id="absent", finished_child=True)
        assert caught.value is observed["failure"]
        order = ["calendar", "pauses", "preparation", "callbacks", "owner"]
        assert observed["order"] == order[:order.index(stage) + 1]
        assert await retained_state(pipeline) == before
        if stage == "owner":
            assert observed["instances"]["owner"].approval_pauses is observed["instances"]["pauses"]
    finally:
        await pipeline.close()


async def test_resume_uses_the_service_captured_in_its_constructed_owner(tmp_path, monkeypatch):
    """Layer: integration. Real absent-pause read uses the same service and grants no authority."""
    pipeline = await pipeline_at(tmp_path)
    try:
        async with pipeline.epic_publication.repository.transaction("composition") as transaction:
            assert await transaction.approval_pauses.latest() is None
        before = await retained_state(pipeline)
        observed = observe_construction(monkeypatch)
        result = await pipeline.resume_epic_approval(session_id="composition", approval_id="absent", finished_child=True)
        assert result is None
        assert observed["order"] == ["calendar", "pauses", "preparation", "callbacks", "owner", "request"]
        instances = observed["instances"]
        assert instances["owner"].approval_pauses is instances["pauses"] is instances["request"]
        assert await retained_state(pipeline) == before
    finally:
        await pipeline.close()
