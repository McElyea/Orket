"""Application boundary for manual wake admission, inspection and controls."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_governed_agent_wake_control_repository import AsyncGovernedAgentWakeControlRepository
from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.application.services.governed_agent_runtime import governed_agent_wake_view
from orket.application.services.governed_agent_wake_control_service import (
    GovernedAgentWakeControlService,
    governed_agent_wake_action_view,
)
from orket.application.services.governed_agent_wake_ingress_service import GovernedAgentWakeIngressService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeControlRepository,
    GovernedAgentWakeRepository,
)


class GovernedAgentWakeCommands:
    def __init__(
        self, repository: GovernedAgentWakeRepository, control_repository: GovernedAgentWakeControlRepository,
        *, now_utc: Callable[[], str],
    ) -> None:
        self._repository = repository
        self._controls = GovernedAgentWakeControlService(control_repository)
        self._ingress = GovernedAgentWakeIngressService(wake_repository=repository, now_utc=now_utc)

    async def enqueue(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        result = await self._ingress.enqueue(payload, source="manual")
        if result.status == "conflict" or result.wake is None:
            return {"ok": False, "error": "E_AGENT_WAKE_CONFLICT"}
        return {
            "ok": True, "object_type": "governed_agent_wake_admission",
            "schema_version": "governed_agent_wake_admission.v1",
            "status": result.status, "wake": governed_agent_wake_view(result.wake),
        }

    async def list_wakes(self, *, target_run_id: str | None) -> dict[str, Any]:
        wakes = await self._repository.list_wakes(target_run_id=target_run_id)
        return {
            "ok": True, "object_type": "governed_agent_wake_list", "schema_version": "governed_agent_wake_list.v1",
            "items": [governed_agent_wake_view(wake) for wake in wakes],
        }

    async def inspect(self, *, wake_id: str) -> dict[str, Any]:
        wake = await self._repository.get_wake(wake_id=wake_id)
        if wake is None:
            raise ValueError("E_AGENT_WAKE_NOT_FOUND")
        return {
            "ok": True, "object_type": "governed_agent_wake_inspection",
            "schema_version": "governed_agent_wake_inspection.v1", "wake": governed_agent_wake_view(wake),
        }

    async def list_actions(self, *, wake_id: str) -> dict[str, Any]:
        if await self._repository.get_wake(wake_id=wake_id) is None:
            raise ValueError("E_AGENT_WAKE_NOT_FOUND")
        actions = await self._controls.list_actions(wake_id=wake_id)
        return {
            "ok": True, "object_type": "governed_agent_wake_action_list",
            "schema_version": "governed_agent_wake_action_list.v1",
            "items": [governed_agent_wake_action_view(action) for action in actions],
        }

    async def control(self, command: str, *, wake_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if command == "cancel":
            result = await self._controls.cancel(wake_id=wake_id, payload=payload)
        elif command == "recover":
            result = await self._controls.recover(wake_id=wake_id, payload=payload)
        else:
            raise ValueError("E_AGENT_WAKE_CONTROL_COMMAND_UNKNOWN")
        successful = result.status in {"applied", "idempotent"}
        return {
            "ok": successful, "error": None if successful else "E_AGENT_WAKE_CONTROL_CONFLICT",
            "object_type": "governed_agent_wake_control_result",
            "schema_version": "governed_agent_wake_control_result.v1", "status": result.status,
            "wake": None if result.wake is None else governed_agent_wake_view(result.wake),
            "action": governed_agent_wake_action_view(result.action),
        }


def build_governed_agent_wake_commands(
    db_path: Path, *, runtime_inputs: RuntimeInputService | None = None,
) -> GovernedAgentWakeCommands:
    inputs = runtime_inputs if runtime_inputs is not None else RuntimeInputService()
    return GovernedAgentWakeCommands(
        AsyncGovernedAgentWakeRepository(db_path), AsyncGovernedAgentWakeControlRepository(db_path),
        now_utc=lambda: inputs.utc_now().isoformat(timespec="microseconds").replace("+00:00", "Z"),
    )
