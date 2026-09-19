"""Unit: workload policy capture and compile value contracts."""
from __future__ import annotations

import pytest

from orket.extensions.contracts import RunPlan
from orket.extensions.workload_executor_support import compile_workload
from orket.extensions.workload_policy import capture_workload_policy

pytestmark = pytest.mark.unit


def test_workload_policy_reliable_mode_enabled_default() -> None:
    """Layer: unit. Default policy uses the canonical capture boundary."""
    assert capture_workload_policy().reliable_mode_enabled is True


def test_compile_workload_contract() -> None:
    """Layer: unit. Compile callback still produces the declared run plan."""
    class _Workload:
        workload_id = "demo_v1"
        workload_version = "1.0.0"

        def compile(self, input_config):
            return RunPlan(workload_id="demo_v1", workload_version="1.0.0", actions=())

    run_plan = compile_workload(_Workload(), {"seed": 1}, None)
    assert run_plan.workload_id == "demo_v1"
