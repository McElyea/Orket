"""Complete runtime inputs flow through the legacy extension action owner."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.exceptions import CardNotFound
from orket.extensions import manager as manager_module
from orket.extensions import workload_executor as workload_executor_module
from orket.extensions.contracts import RunAction, RunPlan
from orket.extensions.manager import ExtensionManager
from orket.extensions.runtime import ExtensionEngineAdapter
from orket.extensions.workload_executor_support import execute_plan_actions
from orket.orchestration.engine import OrchestrationEngine
from tests.helpers.runtime_result import published_result
from tests.runtime.test_extension_manager import _init_test_extension_repo


def _inputs(root: Path, environment: dict[str, str] | None = None) -> RuntimeConstructionInputs:
    return RuntimeConstructionInputs(
        invocation_root=root.resolve(),
        environment={} if environment is None else environment,
        user_settings_json="{}",
        user_preferences_json="{}",
    )


async def _assert_durable_success(manager: ExtensionManager, result) -> None:
    control_plane = manager.workload_executor.control_plane
    run_id = result.control_plane["control_plane_run_id"]
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)
    assert run is not None and truth is not None
    assert run.final_truth_record_id == truth.final_truth_record_id
    assert truth.final_truth_record_id == result.control_plane["control_plane_final_truth_record_id"]
    assert truth.result_class.value == result.control_plane["control_plane_final_result_class"] == "success"


# Layer: contract. Full inputs are exclusive with the manager's legacy root/environment selectors.
@pytest.mark.parametrize("legacy_argument", ["invocation_root", "environment"])
def test_extension_manager_refuses_ambiguous_complete_inputs(
    tmp_path: Path, legacy_argument: str,
) -> None:
    inputs = _inputs(tmp_path)
    options = {legacy_argument: tmp_path if legacy_argument == "invocation_root" else {}}
    with pytest.raises(ValueError, match="E_EXT_CONSTRUCTION_INPUTS_AMBIGUOUS"):
        ExtensionManager(construction_inputs=inputs, **options)


# Layer: contract. Explicit empty values remain authoritative through manager/executor construction.
def test_extension_manager_retains_complete_empty_inputs(tmp_path: Path) -> None:
    inputs = _inputs(tmp_path)
    manager = ExtensionManager(
        catalog_path=Path("catalog.json"),
        project_root=Path("project"),
        construction_inputs=inputs,
    )
    assert manager.catalog_path == tmp_path / "catalog.json"
    assert manager.project_root == tmp_path / "project"
    assert manager.workload_executor._construction_inputs is inputs
    assert manager._operation_environment() == {}
    assert inputs.user_settings() == {} and inputs.user_preferences() == {}


# Layer: contract. The action helper admits the exact explicit object before interaction awaits.
@pytest.mark.asyncio
async def test_action_helper_routes_exact_inputs_before_interaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)
    observed: list[object] = []

    class Adapter:
        async def execute_action(self, action: RunAction) -> dict[str, object]:
            observed.append(("action", action.target))
            return published_result(session_id=action.target)

    @asynccontextmanager
    async def open_spy(context, *, construction_inputs=None):  # type: ignore[no-untyped-def]
        observed.append(("open", context.workspace, construction_inputs))
        try:
            yield Adapter()
        finally:
            observed.append("closed")

    async def emit_event(kind, payload):  # type: ignore[no-untyped-def]
        observed.append(("event", kind, dict(payload)))

    monkeypatch.setattr(ExtensionEngineAdapter, "open", staticmethod(open_spy))
    result = await execute_plan_actions(
        run_plan=RunPlan("route", "1", (RunAction("run_card", "fixture"),)),
        workspace=Path("workspace"),
        department="core",
        interaction_context=SimpleNamespace(emit_event=emit_event),
        construction_inputs=inputs,
    )

    assert observed[0] == ("open", Path("workspace"), inputs)
    assert [row[0] for row in observed[1:4]] == ["event", "event", "event"]
    assert observed[4:] == [("action", "fixture"), "closed"]
    assert result["action_count"] == 1


# Layer: integration. A real legacy workload carries manager inputs into the action helper.
@pytest.mark.asyncio
async def test_manager_executor_routes_exact_inputs_to_legacy_action_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "legacy-source"
    await run_owned_thread(partial(repo.mkdir, parents=True), label="legacy-input-propagation-source-root")
    await run_owned_thread(partial(_init_test_extension_repo, repo), label="legacy-input-propagation-source")
    selected_environment = dict(os.environ)
    selected_environment.update({
        "A106_EXTENSION_INPUT_MARKER": "selected",
        "ORKET_EXT_SECURITY_MODE": "enforce",
        "ORKET_EXT_SECURITY_PROFILE": "development",
    })
    inputs = _inputs(tmp_path, selected_environment)
    manager = await run_owned_thread(
        partial(
            ExtensionManager,
            catalog_path=tmp_path / "catalog.json",
            project_root=tmp_path,
            construction_inputs=inputs,
        ),
        label="legacy-input-propagation-manager",
    )
    monkeypatch.setenv("A106_EXTENSION_INPUT_MARKER", "ambient-install")
    monkeypatch.setenv("ORKET_EXT_SECURITY_MODE", "enforce")
    monkeypatch.setenv("ORKET_EXT_SECURITY_PROFILE", "production")
    installed = await manager.install_from_repo(str(repo))
    assert installed.security_mode == "enforce"
    assert installed.security_profile == "development"
    assert installed.trust_profile == "development"
    assert installed.compat_fallbacks == ("DEV_PROFILE_EXCEPTION_LOCAL_PATH",)
    routed: list[RuntimeConstructionInputs | None] = []
    integrity: list[dict[str, object]] = []
    original = workload_executor_module.execute_plan_actions
    observe_commit = manager_module.observe_commit_in_worker

    async def observe_route(**kwargs):  # type: ignore[no-untyped-def]
        routed.append(kwargs.get("construction_inputs"))
        return await original(**kwargs)

    def observe_integrity(*args, **kwargs):  # type: ignore[no-untyped-def]
        environment = kwargs.get("environment")
        is_mapping = isinstance(environment, dict)
        integrity.append({
            "exact_selected": is_mapping and environment == selected_environment,
            "marker": environment.get("A106_EXTENSION_INPUT_MARKER") if is_mapping else None,
            "security_mode": environment.get("ORKET_EXT_SECURITY_MODE") if is_mapping else None,
            "security_profile": environment.get("ORKET_EXT_SECURITY_PROFILE") if is_mapping else None,
        })
        return observe_commit(*args, **kwargs)

    monkeypatch.setattr(workload_executor_module, "execute_plan_actions", observe_route)
    monkeypatch.setattr(manager_module, "observe_commit_in_worker", observe_integrity)
    monkeypatch.setenv("A106_EXTENSION_INPUT_MARKER", "ambient-integrity")
    result = await manager.run_workload(
        workload_id="mystery_v1",
        input_config={},
        workspace=tmp_path / "workspace",
        department="core",
    )

    routed_exact = len(routed) == 1 and routed[0] is inputs
    assert routed_exact
    assert integrity == [{
        "exact_selected": True,
        "marker": "selected",
        "security_mode": "enforce",
        "security_profile": "development",
    }]
    assert result.workload_id == "mystery_v1"
    await _assert_durable_success(manager, result)


# Layer: integration. The actual engine uses explicit inputs and closes on real runtime refusal.
@pytest.mark.asyncio
async def test_explicit_inputs_bypass_capture_in_actual_legacy_engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _inputs(tmp_path)
    owners: list[OrchestrationEngine] = []
    original = OrchestrationEngine

    async def refuse_capture(cls, **_options):  # type: ignore[no-untyped-def]
        pytest.fail("Explicit legacy inputs cannot trigger ambient recapture")

    def construct(*args, **kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["construction_inputs"] is inputs
        owner = original(*args, **kwargs)
        owners.append(owner)
        return owner

    monkeypatch.setattr(RuntimeConstructionInputs, "capture_async", classmethod(refuse_capture))
    monkeypatch.setattr("orket.extensions.runtime.OrchestrationEngine", construct)
    try:
        with pytest.raises(CardNotFound, match="missing-card"):
            await execute_plan_actions(
                run_plan=RunPlan("actual", "1", (RunAction("run_card", "missing-card"),)),
                workspace=Path("workspace"),
                department="core",
                interaction_context=None,
                construction_inputs=inputs,
            )
        assert len(owners) == 1
        assert owners[0].runtime_context.construction_inputs is inputs
        assert owners[0].workspace_root == tmp_path / "workspace"
        assert owners[0]._closed and owners[0]._pipeline._closed
    finally:
        for owner in owners:
            await owner.close()
