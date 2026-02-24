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
