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
