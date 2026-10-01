"""Integration: borrowed runtime lifetimes do not lend ContextVar tokens to caller tasks."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext

import pytest

from orket.adapters.observability.logging_context import bind_logging, prepare_logging, selected_logging
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime import CompositionConfig
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.helpers.webhook import application

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def runtime_manager(kind, root):
    if kind in {"engine", "pipeline"}:
        owner_type = OrchestrationEngine if kind == "engine" else ExecutionPipeline
        return owner_type.open(root / "workspace", config_root=root, db_path=str(root / "runtime.db")), lambda value: value
    app = create_api_app(CompositionConfig(project_root=root)) if kind == "api" else application(root)
    key = "api_runtime_context" if kind == "api" else "webhook_runtime"
    return app.router.lifespan_context(app), lambda _value: getattr(app.state, key)


async def enter_runtime(manager, select_owner, selected):
    with bind_logging(selected) if selected is not None else nullcontext():
        before = selected_logging(required=False)
        owner = select_owner(await manager.__aenter__())
        after = selected_logging(required=False)
        return owner, before, after


async def exit_runtime(manager, selected):
    with bind_logging(selected):
        before = selected_logging(required=False)
        try:
            await manager.__aexit__(None, None, None)
        except Exception as error:  # Test observation boundary preserves the actual context-reset refusal.
            return error, before, selected_logging(required=False)
        return None, before, selected_logging(required=False)


def runtime_closed(owner, kind):
    if kind == "engine":
        return owner._closed and owner._pipeline._closed
    if kind == "pipeline":
        return owner._closed
    if kind == "api":
        return owner.closed and owner.engine._closed and owner.active_background_task_count == 0
    return owner.closed and owner.client.is_closed


@pytest.mark.parametrize("kind", ["engine", "pipeline", "api", "webhook"])
@pytest.mark.parametrize("outer_binding", [False, True], ids=["unbound-caller", "bound-caller"])
async def test_borrowed_lifetime_can_enter_and_exit_in_distinct_tasks_without_logging_leak(
    tmp_path, monkeypatch, record_property, kind, outer_binding,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    before = selected_logging(required=False)
    first = await prepare_logging(LoggingInputs(tmp_path / "first-caller")) if outer_binding else before
    second = await prepare_logging(LoggingInputs(tmp_path / "second-caller"))
    manager, select_owner = runtime_manager(kind, tmp_path / "runtime")
    owner, entered_before, entered_after = await asyncio.create_task(enter_runtime(manager, select_owner, first))
    try:
        error, exited_before, exited_after = await asyncio.create_task(exit_runtime(manager, second))
        closed_before_emergency = runtime_closed(owner, kind)
        record_property("borrowed_owner_context", {
            "owner": kind, "outer_binding": outer_binding, "enter_context_preserved": entered_after is entered_before,
            "exit_context_preserved": exited_after is exited_before, "exit_error": repr(error),
            "closed_before_emergency": closed_before_emergency, "parent_context_preserved": selected_logging(required=False) is before,
        })
        assert error is None and closed_before_emergency
        assert entered_before is first and entered_after is entered_before
        assert exited_before is second and exited_after is exited_before
        assert selected_logging(required=False) is before
    finally:
        await owner.close()
