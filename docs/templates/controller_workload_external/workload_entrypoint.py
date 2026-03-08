from __future__ import annotations

from typing import Any

from orket.extensions.controller_workload_runtime import build_controller_workload_runtime
from orket_extension_sdk import WorkloadResult
from orket_extension_sdk.workloads.controller import ControllerWorkloadRunner


class ControllerWorkload:
    """Compatibility adapter that delegates execution to the SDK optional layer."""

    async def run(self, ctx: Any, payload: dict[str, Any]) -> WorkloadResult:
        request_payload = dict(payload or {})
        runtime = build_controller_workload_runtime(ctx=ctx, payload=request_payload)
        runner = ControllerWorkloadRunner(runtime=runtime)
        return await runner.run(
            ctx=ctx,
            payload=request_payload,
        )
