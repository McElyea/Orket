from __future__ import annotations

from typing import Any

from orket.kernel.v1 import api as kernel_api


class KernelV1Gateway:
    """Application-facing gateway for the kernel v1 API surface."""

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.start_run(request)

    def execute_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.execute_turn(request)

    def finish_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.finish_run(request)

    def resolve_capability(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.resolve_capability(request)

    def authorize_tool_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.authorize_tool_call(request)

    def replay_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.replay_run(request)

    def compare_runs(self, request: dict[str, Any]) -> dict[str, Any]:
        return kernel_api.compare_runs(request)

    def run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: list[dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        start_payload = {
            "contract_version": "kernel_api/v1",
            "workflow_id": workflow_id,
        }
        if isinstance(start_request, dict):
            start_payload.update(start_request)

        start_response = self.start_run(start_payload)
        run_handle = start_response["run_handle"]

        turns: list[dict[str, Any]] = []
        for request in execute_turn_requests:
            payload = {"contract_version": "kernel_api/v1", **request, "run_handle": run_handle}
            turns.append(self.execute_turn(payload))

        finish_response = self.finish_run(
            {
                "contract_version": "kernel_api/v1",
                "run_handle": run_handle,
                "outcome": finish_outcome,
            }
        )
        return {
            "start": start_response,
            "turns": turns,
            "finish": finish_response,
        }
