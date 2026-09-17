"""Application-owned inspection and operator commands for a governed agent store."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_run_control_repository import AsyncGovernedAgentRunControlRepository
from orket.adapters.storage.async_governed_agent_wake_control_repository import AsyncGovernedAgentWakeControlRepository
from orket.adapters.storage.async_governed_agent_wake_repository import AsyncGovernedAgentWakeRepository
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.application.services.governed_agent_execution_composition import (
    build_governed_agent_operator_service,
    build_governed_agent_replay_repository,
)
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.application.services.governed_agent_run_control_service import GovernedAgentRunControlService


class UnownedGovernedAgentInvoker:
    async def invoke_once(self, **_: Any) -> Any:
        raise RuntimeError("E_AGENT_CLI_INVOKER_NOT_CONFIGURED")

    async def cancel_and_reap(self, **_: Any) -> bool:
        # This caller cannot attest teardown of a child owned by another runtime.
        return False


def build_governed_agent_inspector(
    db_path: Path, *, iterations: AsyncGovernedAgentRepository | None = None,
) -> GovernedAgentInspectionService:
    iterations = iterations if iterations is not None else AsyncGovernedAgentRepository(db_path)
    return GovernedAgentInspectionService(
        replay_repository=build_governed_agent_replay_repository(db_path),
        iteration_repository=iterations,
        call_repository=iterations,
        wake_repository=AsyncGovernedAgentWakeRepository(db_path),
        record_repository=AsyncControlPlaneRecordRepository(db_path),
        pending_gate_repository=AsyncPendingGateRepository(db_path),
        wake_control_repository=AsyncGovernedAgentWakeControlRepository(db_path),
    )


class GovernedAgentCommands:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def inspect(self, *, run_id: str, replay: bool = False) -> dict[str, Any]:
        inspector = build_governed_agent_inspector(self._db_path)
        payload = await inspector.replay(run_id=run_id) if replay else await inspector.inspect(run_id=run_id)
        if payload is None:
            raise ValueError("E_AGENT_RUN_NOT_FOUND")
        return {"ok": not replay or payload["status"] == "matched", **payload}

    async def request_control(self, *, run_id: str, command: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if command not in {"pause", "stop"}:
            raise ValueError("E_AGENT_RUN_CONTROL_COMMAND_UNKNOWN")
        service = GovernedAgentRunControlService(AsyncGovernedAgentRunControlRepository(self._db_path))
        result = await service.request(run_id, {**payload, "command": command})
        return {"ok": result["status"] in {"requested", "idempotent"}, **result}

    async def cancel(
        self, *, run_id: str, action_id: str, actor_ref: str, timestamp_utc: str,
        reason: str, cancellation_epoch: int,
    ) -> dict[str, Any]:
        operator = build_governed_agent_operator_service(
            db_path=self._db_path, iterations=AsyncGovernedAgentRepository(self._db_path),
            invoker=UnownedGovernedAgentInvoker(),
        )
        cancelled = await operator.cancel_run(
            run_id=run_id, action_id=action_id, actor_ref=actor_ref, timestamp_utc=timestamp_utc,
            reason=reason, cancellation_epoch=cancellation_epoch, grace_period_seconds=0,
        )
        return {
            "ok": True, "object_type": "governed_agent_cancellation_result",
            "run": cancelled.run.model_dump(mode="json"),
            "operator_action": cancelled.action.model_dump(mode="json"),
            "final_truth": cancelled.final_truth.model_dump(mode="json"),
            "child_confirmed_stopped": cancelled.child_confirmed_stopped,
        }
