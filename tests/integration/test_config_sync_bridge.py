"""Direct synchronous entrypoints refuse event-loop work without leaking coroutines."""
import asyncio
import inspect
from functools import partial

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.config.config_loader import ConfigLoader
from orket.runtime.config.runtime_context import OrketRuntimeContext
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.schema import EpicConfig


@pytest.mark.contract
@pytest.mark.asyncio
@pytest.mark.parametrize("method,arguments", [
    ("load_organization", ()), ("load_department", ("core",)),
    ("load_asset", ("epics", "missing", EpicConfig)),
    ("list_assets", ("epics",)), ("_load_asset_raw", ("epics", "missing", "core")),
])
async def test_sync_config_methods_refuse_before_coroutine_execution(tmp_path, monkeypatch, method, arguments):
    loader = await run_owned_thread(partial(ConfigLoader, tmp_path), label="config-guard-fixture")
    calls, coroutines = [], []

    async def observe():
        calls.append("executed")

    def operation(*_args):
        coroutine = observe()
        coroutines.append(coroutine)
        return coroutine

    monkeypatch.setattr(loader, method + "_async", operation)
    with pytest.raises(RuntimeError, match="E_CONFIG_LOADER_REQUIRES_ASYNC_METHOD"):
        getattr(loader, method)(*arguments)
    assert calls == [] and len(coroutines) == 1
    assert inspect.getcoroutinestate(coroutines[0]) == inspect.CORO_CLOSED


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["engine", "pipeline", "context"])
async def test_direct_runtime_construction_refuses_before_filesystem_effects(tmp_path, monkeypatch, kind):
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspace"
    options = dict(db_path=str(tmp_path / "runtime.db"), config_root=tmp_path)
    factories = {
        "engine": partial(OrchestrationEngine, workspace, **options),
        "pipeline": partial(ExecutionPipeline, workspace, **options),
        "context": partial(OrketRuntimeContext.from_env, workspace_root=workspace,
                           config_loader_factory=ConfigLoader, run_ledger_repo=object(), **options),
    }
    before = await asyncio.to_thread(lambda: sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")))
    owner = None
    try:
        with pytest.raises(RuntimeError, match="E_RUNTIME_CONSTRUCTION_REQUIRES_ASYNC_OWNER"):
            owner = factories[kind]()
        after = await asyncio.to_thread(lambda: sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*")))
        assert before == after
    finally:
        if owner is not None:
            await owner.close()
