from __future__ import annotations

from orket.application.services.kernel_v1_gateway import KernelV1Gateway


def test_kernel_v1_gateway_uses_api_surface() -> None:
    gateway = KernelV1Gateway()
    start = gateway.start_run({"contract_version": "kernel_api/v1", "workflow_id": "wf-gateway"})
    run_handle = start["run_handle"]
    assert run_handle["contract_version"] == "kernel_api/v1"

    resolve = gateway.resolve_capability(
        {
            "contract_version": "kernel_api/v1",
            "role": "coder",
            "task": "edit",
            "context": {"capability_enforcement": True},
        }
    )
    assert resolve["capability_plan"]["mode"] == "enabled"


def test_kernel_v1_gateway_run_lifecycle_minimal_path() -> None:
    gateway = KernelV1Gateway()
    lifecycle = gateway.run_lifecycle(
        workflow_id="wf-lifecycle",
        execute_turn_requests=[
            {
                "turn_id": "turn-0001",
                "commit_intent": "stage_only",
                "turn_input": {},
            }
        ],
        finish_outcome="PASS",
    )
    assert lifecycle["start"]["contract_version"] == "kernel_api/v1"
    assert len(lifecycle["turns"]) == 1
    assert lifecycle["turns"][0]["contract_version"] == "kernel_api/v1"
    assert lifecycle["finish"]["outcome"] == "PASS"
