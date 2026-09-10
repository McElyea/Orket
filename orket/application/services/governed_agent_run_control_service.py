from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol

from orket.application.services.governed_agent_effect_control_support import _utc_timestamp
from orket.core.contracts import OperatorActionRecord
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from orket.core.domain.governed_agent_continuation import GovernedAgentContinuationInputs


class GovernedAgentRunControlRepository(Protocol):
    async def list_controls(self, invocation_id: str) -> tuple[OperatorActionRecord, ...]: ...

    async def submit(self, invocation_id: str, action: OperatorActionRecord) -> str: ...


class GovernedAgentRunControlService:
    def __init__(self, repository: GovernedAgentRunControlRepository) -> None:
        self._repository = repository

    async def request(self, run_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        fields = {"action_id", "actor_ref", "timestamp_utc", "invocation_id", "command"}
        if set(payload) != fields or any(not isinstance(payload[field], str) or not str(payload[field]).strip()
                                        for field in fields):
            raise ValueError("E_AGENT_RUN_CONTROL_PAYLOAD_INVALID")
        commands = {"pause": OperatorCommandClass.PAUSE_RUN, "stop": OperatorCommandClass.MARK_TERMINAL}
        if payload["command"] not in commands:
            raise ValueError("E_AGENT_RUN_CONTROL_COMMAND_INVALID")
        invocation = str(payload["invocation_id"])
        action = OperatorActionRecord(
            action_id=str(payload["action_id"]), actor_ref=str(payload["actor_ref"]),
            timestamp=_utc_timestamp(payload["timestamp_utc"]), target_ref=run_id,
            precondition_basis_ref=f"agent-control:{invocation}", input_class=OperatorInputClass.COMMAND,
            command_class=commands[str(payload["command"])], result="requested",
            affected_transition_refs=[f"agent-decision:{invocation}"],
        )
        status = await self._repository.submit(invocation, action)
        return {"status": status, "action": action.model_dump(mode="json"),
                "boundary": "after_current_iteration_before_next_dispatch"}


async def with_operator_controls(
    inputs: GovernedAgentContinuationInputs, repository: GovernedAgentRunControlRepository | None,
    invocation_id: str,
) -> GovernedAgentContinuationInputs:
    controls = () if repository is None else await repository.list_controls(invocation_id)
    return replace(inputs,
                   accepted_pause=any(item.command_class is OperatorCommandClass.PAUSE_RUN for item in controls),
                   accepted_terminal_stop=any(item.command_class is OperatorCommandClass.MARK_TERMINAL for item in controls),
                   operator_action_refs=tuple(item.action_id for item in controls))
