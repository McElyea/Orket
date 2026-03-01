from __future__ import annotations

from typing import Any, Dict, List, Optional

from orket.application.services.kernel_v1_gateway import KernelV1Gateway


class KernelGatewayProxy:
    """Thin proxy that exposes kernel lifecycle APIs."""

    def __init__(self, kernel_gateway: KernelV1Gateway) -> None:
        self.kernel_gateway = kernel_gateway

    def start_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.start_run(request)

    def execute_turn(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.execute_turn(request)

    def finish_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.finish_run(request)

    def resolve_capability(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.resolve_capability(request)

    def authorize_tool_call(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.authorize_tool_call(request)

    def replay_run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.replay_run(request)

    def compare_runs(self, request: Dict[str, Any]) -> Dict[str, Any]:
        return self.kernel_gateway.compare_runs(request)

    def run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: List[Dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.kernel_gateway.run_lifecycle(
            workflow_id=workflow_id,
            execute_turn_requests=execute_turn_requests,
            finish_outcome=finish_outcome,
            start_request=start_request,
        )
