"""Owned runtime factories capture constructor inputs and retain real failure truth."""
import asyncio
from pathlib import Path

import pytest

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.exceptions import CardNotFound
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.conftest import OrgBuilder

pytestmark = pytest.mark.integration
RUNTIMES = [OrchestrationEngine, ExecutionPipeline]


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_type", RUNTIMES, ids=["engine", "pipeline"])
async def test_owned_runtime_uses_explicit_snapshot_without_recapture(tmp_path, monkeypatch, runtime_type):
    monkeypatch.chdir(tmp_path)
    inputs = await RuntimeConstructionInputs.capture_async()

    async def refuse(cls, **options):
        pytest.fail("Explicit construction inputs cannot trigger ambient recapture")

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(refuse))
    async with runtime_type.open(Path("workspace"), construction_inputs=inputs) as owner:
        assert owner.runtime_context.construction_inputs is inputs
        await owner.initialize()
    assert owner._closed


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_type", RUNTIMES, ids=["engine", "pipeline"])
async def test_owned_runtime_retains_workspace_config_and_environment(tmp_path, monkeypatch, runtime_type):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_ORG_NAME", "admitted")
    await asyncio.to_thread((tmp_path / "config-root").mkdir)
    await asyncio.to_thread(OrgBuilder().write, tmp_path / "config-root")
    entered, release = asyncio.Event(), asyncio.Event()
    original = RuntimeConstructionInputs.capture_async

    async def capture(cls, **options):
        result = await original(**options)
        entered.set()
        await release.wait()
        return result

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(capture))
    options = {"config_root": Path("config-root"), "db_path": "runtime.db"}

    async def run():
        async with runtime_type.open(Path("workspace"), **options) as owner:
            assert owner.org.name == "admitted"
            assert owner.runtime_context.workspace_root == tmp_path / "workspace"
            assert owner.config_root == tmp_path / "config-root"
            assert owner.db_path == str(tmp_path / "runtime.db")
            await owner.initialize()
        assert owner._closed

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        options.update(config_root=Path("mutated"), db_path="mutated.db")
        monkeypatch.setenv("ORKET_ORG_NAME", "mutated")
        monkeypatch.chdir(tmp_path.parent)
        release.set()
        await asyncio.wait_for(task, 5)
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("runtime_type", RUNTIMES, ids=["engine", "pipeline"])
async def test_owned_runtime_real_missing_card_closes_before_error(tmp_path, monkeypatch, runtime_type):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CardNotFound, match="missing-card"):
        async with runtime_type.open(tmp_path / "workspace", config_root=tmp_path) as owner:
            await owner.run_card("missing-card")
    assert owner._closed
    if isinstance(owner, OrchestrationEngine):
        assert owner._pipeline._closed


@pytest.mark.parametrize("runtime_type", RUNTIMES, ids=["engine", "pipeline"])
def test_runtime_constructor_remains_available_before_loop(tmp_path, monkeypatch, runtime_type):
    monkeypatch.chdir(tmp_path)
    owner = runtime_type(tmp_path / "workspace", config_root=tmp_path)

    async def run():
        try:
            await owner.initialize()
        finally:
            await owner.close()

    asyncio.run(run())
    assert owner._closed
