from __future__ import annotations

# Layer: contract/unit/integration
from pathlib import Path
from typing import Any

import pytest

from orket.extensions import controller_observability
from orket.extensions.controller_dispatcher import (
    ERROR_CHILD_TIMEOUT_INVALID,
    ERROR_MAX_DEPTH_EXCEEDED,
    ControllerDispatcher,
)
from orket.extensions.manager import ExtensionManager
from orket.extensions.models import CONTRACT_STYLE_SDK_V0
from orket_extension_sdk.capabilities import CapabilityRegistry
from orket_extension_sdk.controller import ControllerChildResult, ControllerPolicyCaps, ControllerRunSummary
from orket_extension_sdk.workload import WorkloadContext
from orket_extension_sdk.workloads.controller import ControllerWorkloadRunner, ControllerWorkloadRuntime
from tests.runtime.test_controller_dispatcher import (
    _extension_result,
    _init_controller_bootstrap_repo,
    _init_sdk_child_repo,
    _StubExtensionManager,
)


@pytest.mark.asyncio
async def test_observability_batch_is_ordered_and_schema_valid() -> None:
    """Layer: contract."""
    summary = ControllerRunSummary(
        controller_workload_id="controller_workload_v1",
        status="failed",
        requested_caps=ControllerPolicyCaps(max_depth=2, max_fanout=3, child_timeout_seconds=30),
        enforced_caps=ControllerPolicyCaps(max_depth=1, max_fanout=3, child_timeout_seconds=20),
        error_code="controller.child_execution_failed",
        child_results=[
            ControllerChildResult(target_workload="sdk_child_a_v1", status="success", requested_timeout=30, enforced_timeout=20),
            ControllerChildResult(
                target_workload="sdk_child_b_v1",
                status="failed",
                requested_timeout=30,
                enforced_timeout=20,
                normalized_error="controller.child_execution_failed",
            ),
            ControllerChildResult(
                target_workload="sdk_child_c_v1",
                status="not_attempted",
                requested_timeout=30,
                enforced_timeout=None,
                normalized_error=None,
            ),
        ],
    )
    events = await controller_observability.emit_observability_batch(
        run_id="run_1",
        envelope_payload={"parent_depth": 0, "children": [{}, {}, {}]},
        summary=summary,
    )

    assert events[0]["event"] == "controller_run"
    assert [event["event"] for event in events[1:]] == ["controller_child", "controller_child", "controller_child"]
    assert [event["status"] for event in events[1:]] == ["success", "failure", "not_attempted"]
    assert events[0]["accepted_fanout"] == 3
    assert events[0]["declared_fanout"] == 3
    assert events[0]["result"] == "failed"
    assert events[0]["error_code"] == "controller.child_execution_failed"
    assert events[0]["projection_source"] == controller_observability.CONTROLLER_OBSERVABILITY_PROJECTION_SOURCE
    assert events[0]["projection_only"] is True
    assert all(event["projection_only"] is True for event in events[1:])


@pytest.mark.asyncio
async def test_observability_projection_excludes_run_id() -> None:
    """Layer: unit."""
    summary = ControllerRunSummary(
        controller_workload_id="controller_workload_v1",
        status="blocked",
        error_code="controller.max_depth_exceeded",
        child_results=[],
    )
    events_a = await controller_observability.emit_observability_batch(
        run_id="run_a",
        envelope_payload={"parent_depth": 1, "children": []},
        summary=summary,
    )
    events_b = await controller_observability.emit_observability_batch(
        run_id="run_b",
        envelope_payload={"parent_depth": 1, "children": []},
        summary=summary,
    )

    assert events_a != events_b
    assert controller_observability.canonical_projection(events_a) == controller_observability.canonical_projection(events_b)


@pytest.mark.asyncio
async def test_dispatcher_blocked_mapping_and_not_attempted_timeout_shape() -> None:
    """Layer: unit."""
    manager = _StubExtensionManager(
        workload_styles={"sdk_a": CONTRACT_STYLE_SDK_V0, "sdk_b": CONTRACT_STYLE_SDK_V0},
        outcomes={
            "sdk_a": [_extension_result("sdk_a", ok=False, suffix="a")],
            "sdk_b": [_extension_result("sdk_b", ok=True, suffix="b")],
        },
    )
    dispatcher = ControllerDispatcher(extension_manager=manager)

    blocked = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 1,
            "requested_caps": {"max_depth": 1},
            "ancestry": [],
            "children": [{"target_workload": "sdk_a", "contract_style": "sdk_v0"}],
        },
        workspace=Path(),
        department="core",
    )
    assert blocked.status == "blocked"
    assert blocked.error_code == ERROR_MAX_DEPTH_EXCEEDED

    timeout_blocked = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": [],
            "children": [{"target_workload": "sdk_a", "contract_style": "sdk_v0", "timeout_seconds": 0}],
        },
        workspace=Path(),
        department="core",
    )
    assert timeout_blocked.status == "blocked"
    assert timeout_blocked.error_code == ERROR_CHILD_TIMEOUT_INVALID

    failed = await dispatcher.dispatch(
        payload={
            "controller_contract_version": "controller.workload.v1",
            "controller_workload_id": "controller_workload_v1",
            "parent_depth": 0,
            "ancestry": [],
            "children": [
                {"target_workload": "sdk_a", "contract_style": "sdk_v0"},
                {"target_workload": "sdk_b", "contract_style": "sdk_v0"},
            ],
        },
        workspace=Path(),
        department="core",
    )
    assert failed.status == "failed"
    assert failed.child_results[1].status == "not_attempted"
    assert failed.child_results[1].enforced_timeout is None


def _build_controller_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[ExtensionManager, Path]:
    catalog_path = tmp_path / "extensions_catalog.json"
    monkeypatch.setenv("ORKET_EXTENSIONS_CATALOG", str(catalog_path))
    sdk_a = tmp_path / "sdk_a"
    sdk_b = tmp_path / "sdk_b"
    controller = tmp_path / "controller"
    for repo in (sdk_a, sdk_b, controller):
        repo.mkdir(parents=True, exist_ok=True)
    _init_sdk_child_repo(sdk_a, extension_id="sdk.child.a", workload_id="sdk_child_a_v1")
    _init_sdk_child_repo(sdk_b, extension_id="sdk.child.b", workload_id="sdk_child_b_v1")
    _init_controller_bootstrap_repo(controller)
    manager = ExtensionManager(catalog_path=catalog_path, project_root=tmp_path)
    manager.install_from_repo(str(sdk_a))
    manager.install_from_repo(str(sdk_b))
    manager.install_from_repo(str(controller))
    workspace = tmp_path / "workspace" / "default"
    workspace.mkdir(parents=True, exist_ok=True)
    return manager, workspace


@pytest.mark.asyncio
async def test_controller_workload_observability_emission_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Layer: integration."""
    manager, workspace = _build_controller_manager(tmp_path, monkeypatch)

    run = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "requested_caps": {"max_depth": 2, "max_fanout": 5, "child_timeout_seconds": 30},
            "children": [
                {"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0", "payload": {"token": "a"}},
                {"target_workload": "sdk_child_b_v1", "contract_style": "sdk_v0", "payload": {"token": "b", "fail": True}},
            ],
        },
        workspace=workspace,
        department="core",
    )
    output = run.summary["output"]
    summary = output["controller_summary"]
    events = output["controller_observability_events"]
    run_event = events[0]
    child_events = events[1:]

    assert summary["status"] == "failed"
    assert run_event["event"] == "controller_run"
    assert run_event["result"] == "failed"
    assert run_event["projection_source"] == controller_observability.CONTROLLER_OBSERVABILITY_PROJECTION_SOURCE
    assert run_event["projection_only"] is True
    assert [event["status"] for event in child_events] == ["success", "failure"]
    assert run_event["result"] != "blocked"
    assert output["controller_observability_projection"]
    assert output["controller_observability_error"] is None

    async def _raise_emit_error(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        raise ValueError("forced observability failure")

    async def _success_dispatch(*args: Any, **kwargs: Any) -> ControllerRunSummary:
        return ControllerRunSummary(controller_workload_id="controller_workload_v1", status="success")

    direct_runner = ControllerWorkloadRunner(
        runtime=ControllerWorkloadRuntime(
            dispatch=_success_dispatch,
            emit_observability=_raise_emit_error,
            observability_emit_failed_error_code="controller.observability_emit_failed",
        )
    )
    direct_ctx = WorkloadContext(
        extension_id="controller.test",
        workload_id="controller_workload_v1",
        run_id="controller-test-run",
        workspace_root=workspace,
        input_dir=workspace,
        output_dir=tmp_path / "artifacts",
        capabilities=CapabilityRegistry(),
    )
    fail_closed_result = await direct_runner.run(
        ctx=direct_ctx,
        payload={"controller_workload_id": "controller_workload_v1", "department": "core"},
    )
    fail_output = fail_closed_result.output

    assert fail_output["controller_summary"]["status"] == "failed"
    assert fail_output["controller_summary"]["error_code"] == "controller.observability_emit_failed"
    assert fail_output["controller_observability_events"] == []
    assert fail_output["controller_observability_projection"] == []
    assert "forced observability failure" in str(fail_output["controller_observability_error"] or "")


@pytest.mark.asyncio
async def test_controller_workload_enablement_policy_blocks_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Layer: integration."""
    manager, workspace = _build_controller_manager(tmp_path, monkeypatch)
    monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "0")

    blocked_run = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}],
        },
        workspace=workspace,
        department="core",
    )
    output = blocked_run.summary["output"]
    assert output["controller_summary"]["status"] == "blocked"
    assert output["controller_summary"]["error_code"] == "controller.disabled_by_policy"
    assert output["controller_observability_events"][0]["result"] == "blocked"
    assert output["controller_observability_events"][0]["error_code"] == "controller.disabled_by_policy"
    assert output["controller_observability_events"][0]["projection_only"] is True
    assert output["controller_observability_events"][1:] == []

    monkeypatch.setenv("ORKET_CONTROLLER_ENABLED", "1")
    monkeypatch.setenv("ORKET_CONTROLLER_ALLOWED_DEPARTMENTS", "ops")
    blocked_department_run = await manager.run_workload(
        workload_id="controller_workload_v1",
        input_config={
            "controller_workload_id": "controller_workload_v1",
            "children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}],
        },
        workspace=workspace,
        department="core",
    )
    blocked_department_output = blocked_department_run.summary["output"]
    assert blocked_department_output["controller_summary"]["status"] == "blocked"
    assert blocked_department_output["controller_summary"]["error_code"] == "controller.disabled_by_policy"
    assert blocked_department_output["controller_observability_events"][0]["projection_source"] == (
        controller_observability.CONTROLLER_OBSERVABILITY_PROJECTION_SOURCE
    )
