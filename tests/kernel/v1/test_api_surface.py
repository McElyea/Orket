from __future__ import annotations

from orket.kernel.v1 import (
    authorize_tool_call,
    compare_runs,
    execute_turn,
    finish_run,
    replay_run,
    resolve_capability,
    start_run,
)


def test_kernel_v1_api_exports_are_callable() -> None:
    assert callable(start_run)
    assert callable(execute_turn)
    assert callable(finish_run)
    assert callable(resolve_capability)
    assert callable(authorize_tool_call)
    assert callable(replay_run)
    assert callable(compare_runs)


def test_kernel_v1_api_resolve_capability_round_trip() -> None:
    response = resolve_capability(
        {
            "contract_version": "kernel_api/v1",
            "role": "coder",
            "task": "edit",
            "context": {"capability_enforcement": True},
        }
    )
    assert response["contract_version"] == "kernel_api/v1"
    assert response["capability_plan"]["mode"] == "enabled"
