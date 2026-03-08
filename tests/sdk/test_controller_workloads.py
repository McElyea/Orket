from __future__ import annotations

# Layer: unit

from pathlib import Path
from typing import Any, Mapping

import pytest

from orket_extension_sdk.controller import ControllerChildResult, ControllerRunSummary
from orket_extension_sdk.testing import FakeCapabilities
from orket_extension_sdk.workload import WorkloadContext
from orket_extension_sdk.workloads.controller import (
    ControllerWorkloadRunner,
    ControllerWorkloadRuntime,
    canonical_observability_projection,
)


def _build_context(tmp_path: Path) -> WorkloadContext:
    workspace = tmp_path / "workspace"
    output = tmp_path / "output"
    workspace.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    return WorkloadContext(
        extension_id="ext.controller",
        workload_id="controller_workload_v1",
        run_id="run_123",
        workspace_root=workspace,
        input_dir=workspace,
        output_dir=output,
        capabilities=FakeCapabilities.from_mapping({}),
        config={"department": "core"},
    )


@pytest.mark.asyncio
async def test_controller_workload_runner_success_path(tmp_path: Path) -> None:
    """Layer: unit."""
    ctx = _build_context(tmp_path)
    dispatch_calls: list[dict[str, Any]] = []

    async def dispatch(
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        dispatch_calls.append(
            {
                "envelope": dict(envelope_payload),
                "workspace": str(workspace),
                "department": department,
            }
        )
        return ControllerRunSummary(
            controller_workload_id="controller_workload_v1",
            status="success",
            child_results=[
                ControllerChildResult(
                    target_workload="sdk_child_a_v1",
                    status="success",
                )
            ],
            error_code=None,
        )

    async def emit_observability(
        *,
        run_id: str,
        envelope_payload: Mapping[str, Any],
        summary: ControllerRunSummary,
    ) -> list[dict[str, Any]]:
        _ = (envelope_payload, summary)
        return [
            {
                "event": "controller_run",
                "run_id": run_id,
                "result": "success",
                "error_code": None,
            },
            {
                "event": "controller_child",
                "run_id": run_id,
                "child_index": 0,
                "status": "success",
                "error_code": None,
            },
        ]

    runtime = ControllerWorkloadRuntime(
        dispatch=dispatch,
        emit_observability=emit_observability,
    )
    runner = ControllerWorkloadRunner(runtime=runtime)

    result = await runner.run(
        ctx=ctx,
        payload={
            "requested_caps": {"max_depth": 2, "max_fanout": 3},
            "children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}],
        },
    )

    assert result.ok is True
    assert result.issues == []
    assert dispatch_calls[0]["department"] == "core"
    assert dispatch_calls[0]["envelope"]["controller_contract_version"] == "controller.workload.v1"
    assert dispatch_calls[0]["envelope"]["controller_workload_id"] == "controller_workload_v1"
    projection = result.output["controller_observability_projection"]
    assert all("run_id" not in event for event in projection)
    assert result.output["controller_observability_error"] is None


@pytest.mark.asyncio
async def test_controller_workload_runner_blocks_when_policy_disables(tmp_path: Path) -> None:
    """Layer: unit."""
    ctx = _build_context(tmp_path)
    dispatch_called = False

    async def dispatch(
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        _ = (envelope_payload, workspace, department)
        nonlocal dispatch_called
        dispatch_called = True
        raise AssertionError("dispatch should not be called when runtime policy disables controller")

    async def emit_observability(
        *,
        run_id: str,
        envelope_payload: Mapping[str, Any],
        summary: ControllerRunSummary,
    ) -> list[dict[str, Any]]:
        _ = (run_id, envelope_payload)
        assert summary.status == "blocked"
        assert summary.error_code == "controller.disabled_by_policy"
        return [
            {
                "event": "controller_run",
                "run_id": "run_123",
                "result": "blocked",
                "error_code": "controller.disabled_by_policy",
            }
        ]

    def is_enabled(*, payload: Mapping[str, Any], department: str) -> bool:
        _ = (payload, department)
        return False

    runtime = ControllerWorkloadRuntime(
        dispatch=dispatch,
        emit_observability=emit_observability,
        is_enabled=is_enabled,
    )
    runner = ControllerWorkloadRunner(runtime=runtime)

    result = await runner.run(
        ctx=ctx,
        payload={"children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}]},
    )

    assert dispatch_called is False
    summary = result.output["controller_summary"]
    assert result.ok is False
    assert summary["status"] == "blocked"
    assert summary["error_code"] == "controller.disabled_by_policy"
    assert len(result.issues) == 1


@pytest.mark.asyncio
async def test_controller_workload_runner_fail_closed_on_observability_error(tmp_path: Path) -> None:
    """Layer: unit."""
    ctx = _build_context(tmp_path)

    async def dispatch(
        *,
        envelope_payload: Mapping[str, Any],
        workspace: Path,
        department: str,
    ) -> ControllerRunSummary:
        _ = (envelope_payload, workspace, department)
        return ControllerRunSummary(
            controller_workload_id="controller_workload_v1",
            status="success",
            child_results=[
                ControllerChildResult(
                    target_workload="sdk_child_a_v1",
                    status="success",
                )
            ],
            error_code=None,
        )

    async def emit_observability(
        *,
        run_id: str,
        envelope_payload: Mapping[str, Any],
        summary: ControllerRunSummary,
    ) -> list[dict[str, Any]]:
        _ = (run_id, envelope_payload, summary)
        raise ValueError("forced observability failure")

    runtime = ControllerWorkloadRuntime(
        dispatch=dispatch,
        emit_observability=emit_observability,
        observability_emit_failed_error_code="controller.observability_emit_failed",
    )
    runner = ControllerWorkloadRunner(runtime=runtime)

    result = await runner.run(
        ctx=ctx,
        payload={"children": [{"target_workload": "sdk_child_a_v1", "contract_style": "sdk_v0"}]},
    )

    summary = result.output["controller_summary"]
    assert result.ok is False
    assert summary["status"] == "failed"
    assert summary["error_code"] == "controller.observability_emit_failed"
    assert result.output["controller_observability_events"] == []
    assert result.output["controller_observability_projection"] == []
    assert "forced observability failure" in str(result.output["controller_observability_error"] or "")


def test_canonical_observability_projection_requires_run_id() -> None:
    """Layer: unit."""
    with pytest.raises(ValueError, match="controller.observability_event_invalid"):
        canonical_observability_projection(
            [
                {
                    "event": "controller_run",
                    "result": "success",
                }
            ]
        )
