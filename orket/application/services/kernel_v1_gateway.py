from __future__ import annotations

from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_runtime_owner import KernelRuntime
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1 import api as kernel_api


class KernelV1Gateway:
    """Application-facing gateway for the kernel v1 API surface."""

    def __init__(self, *, runtime_inputs: RuntimeInputService | None = None, invocation_root: Path | None = None) -> None:
        self.runtime = KernelRuntime(runtime_inputs=runtime_inputs, invocation_root=invocation_root)

    def close(self) -> None:
        self.runtime.close()

    def _call(self, operation, request):
        require_sync_context(code="E_KERNEL_INVOCATION_REQUIRES_ASYNC_OWNER")
        captured = capture_kernel_request(request)
        with self.runtime.activate(), self.runtime.lock:
            return operation(captured)

    def start_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.start_run, request)

    def execute_turn(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.execute_turn, request)

    def finish_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.finish_run, request)

    def resolve_capability(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.resolve_capability, request)

    def authorize_tool_call(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.authorize_tool_call, request)

    def replay_run(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.replay_run, request)

    def compare_runs(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.compare_runs, request)

    def projection_pack(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.projection_pack, request)

    def admit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.admit_proposal, request)

    def commit_proposal(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.commit_proposal, request)

    def end_session(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.end_session, request)

    def list_ledger_events(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.list_ledger_events, request)

    def rebuild_pending_approvals(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.rebuild_pending_approvals, request)

    def replay_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.replay_action_lifecycle, request)

    def audit_action_lifecycle(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._call(kernel_api.audit_action_lifecycle, request)

    def run_lifecycle(
        self,
        *,
        workflow_id: str,
        execute_turn_requests: list[dict[str, Any]],
        finish_outcome: str = "PASS",
        start_request: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        captured = capture_kernel_request({"workflow_id": workflow_id, "start_request": start_request,
            "execute_turn_requests": execute_turn_requests, "finish_outcome": finish_outcome})
        start_payload = {
            "contract_version": "kernel_api/v1",
            "workflow_id": captured["workflow_id"],
        }
        if isinstance(captured["start_request"], dict):
            start_payload.update(captured["start_request"])

        start_response = self.start_run(start_payload)
        run_handle = start_response["run_handle"]

        turns: list[dict[str, Any]] = []
        for request in captured["execute_turn_requests"]:
            payload = {"contract_version": "kernel_api/v1", **request, "run_handle": run_handle}
            turns.append(self.execute_turn(payload))

        finish_response = self.finish_run(
            {
                "contract_version": "kernel_api/v1",
                "run_handle": run_handle,
                "outcome": captured["finish_outcome"],
            }
        )
        return {
            "start": start_response,
            "turns": turns,
            "finish": finish_response,
        }
