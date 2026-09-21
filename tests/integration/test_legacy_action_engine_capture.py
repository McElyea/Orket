"""Legacy action admission, direct-call migration and actual runtime refusal."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.exceptions import CardNotFound
from orket.extensions.contracts import RunAction, RunPlan
from orket.extensions.runtime import ExtensionEngineAdapter, RunContext
from orket.extensions.workload_executor_support import execute_plan_actions
from orket.orchestration.engine import OrchestrationEngine
from tests.conftest import OrgBuilder
from tests.helpers.runtime_result import published_result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_action_real_missing_card_closes_engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    owners = []

    def construct(*args, **kwargs):
        owner = OrchestrationEngine(*args, **kwargs)
        owners.append(owner)
        return owner

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", construct)
    plan = RunPlan("missing", "1", (RunAction("run_card", "missing-card"),))
    try:
        with pytest.raises(CardNotFound, match="missing-card"):
            await execute_plan_actions(run_plan=plan, workspace=tmp_path / "workspace",
                                       department="core", interaction_context=None)
        assert len(owners) == 1 and owners[0]._pipeline._initialized
        assert owners[0]._closed and owners[0]._pipeline._closed
    finally:
        for owner in owners:
            await owner.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_plan_and_runtime_inputs_precede_interaction_await(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_ORG_NAME", "admitted")
    await asyncio.to_thread(OrgBuilder().write, tmp_path)
    owners, calls, events = [], [], []
    params, metadata = {"session_id": "original"}, {"marker": "original"}
    plan = RunPlan("capture", "1", (RunAction("run_issue", "fixture", params),), metadata)
    original_hash = plan.plan_hash()

    def construct(*args, **kwargs):
        owner = OrchestrationEngine(*args, **kwargs)
        owners.append(owner)

        async def action(target, **options):
            calls.append((target, options))
            return published_result(session_id=options["session_id"])

        monkeypatch.setattr(owner, "run_card", action)
        return owner

    async def emit_event(kind, payload):
        events.append((kind, payload))
        params["session_id"] = "mutated"
        metadata["marker"] = "mutated"
        monkeypatch.setenv("ORKET_ORG_NAME", "mutated")
        await asyncio.sleep(0)

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", construct)
    try:
        result = await execute_plan_actions(run_plan=plan, workspace=Path("workspace"), department="core",
                                            interaction_context=SimpleNamespace(emit_event=emit_event))
        assert len(events) == 3 and all(row[1]["authoritative"] is False for row in events)
        assert result["plan_hash"] == original_hash and plan.plan_hash() != original_hash
        assert calls == [("fixture", {"session_id": "original"})]
        assert owners[0].org.name == "admitted" and owners[0].workspace_root == tmp_path / "workspace"
        assert owners[0]._closed and owners[0]._pipeline._closed
    finally:
        for owner in owners:
            await owner.close()


@pytest.mark.contract
@pytest.mark.asyncio
async def test_direct_legacy_engine_constructor_refuses_loop_before_effects(tmp_path, monkeypatch):
    constructed = []
    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", lambda *args, **kwargs: constructed.append(args))
    with pytest.raises(RuntimeError, match="E_EXTENSION_ENGINE_REQUIRES_ASYNC_OWNER"):
        ExtensionEngineAdapter(RunContext(tmp_path, "core"))
    assert constructed == []


@pytest.mark.integration
def test_direct_legacy_engine_constructor_remains_available_before_loop(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    owner = ExtensionEngineAdapter(RunContext(tmp_path / "workspace", "core"))
    try:
        assert owner.engine.workspace_root == tmp_path / "workspace"
    finally:
        asyncio.run(owner.close())
    assert owner.engine._closed and owner.engine._pipeline._closed


@pytest.mark.contract
@pytest.mark.asyncio
async def test_empty_legacy_plan_emits_observations_without_constructing_engine(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        pytest.fail("Empty plan cannot construct an engine")

    observed = []

    async def emit_event(kind, payload):
        observed.append((kind, payload))

    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", refuse)
    plan = RunPlan("empty", "1", ())
    result = await execute_plan_actions(run_plan=plan, workspace=tmp_path, department="core",
                                        interaction_context=SimpleNamespace(emit_event=emit_event))
    assert result == {"plan_hash": plan.plan_hash(), "action_count": 0, "action_results": []}
    assert len(observed) == 3
