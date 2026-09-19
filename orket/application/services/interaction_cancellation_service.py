"""Application admission and durable audit of an observed interaction cancellation."""
from collections.abc import Callable
from dataclasses import dataclass

from orket.adapters.execution.owned_io import run_owned_io
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.domain import OperatorCommandClass, OperatorInputClass
from orket.streaming.manager import InteractionManager


class InteractionCancelNotFound(ValueError):
    """The target is not a member of the selected session."""


class InteractionCancelConflict(ValueError):
    """The selected session has no cancellable active turn."""


class InteractionCancelDisabled(ValueError):
    """Stream interactions are disabled for this manager."""


@dataclass(frozen=True)
class InteractionCancellationService:
    manager: InteractionManager
    publication: ControlPlanePublicationService
    utc_now: Callable[[], str]

    async def cancel(self, *, session_id: str, turn_id: str | None, actor_ref: str) -> dict[str, object]:
        manager, publication = self.manager, self.publication
        if not manager.stream_enabled():
            raise InteractionCancelDisabled("Stream events v1 is disabled.")
        target = turn_id or session_id
        actor, timestamp = str(actor_ref).strip(), self.utc_now()

        async def operation() -> dict[str, object]:
            result = await manager.cancel(target, session_id=session_id, session_target=not bool(turn_id),
                                          timestamp=timestamp)
            if result.status == "not_found":
                raise InteractionCancelNotFound("Interaction cancellation target not found in this session.")
            if result.status != "cancelled":
                raise InteractionCancelConflict("Interaction has no cancellable active turn.")
            if actor:
                target_ref = f"interaction-turn:{target}" if turn_id else f"interaction-session:{session_id}"
                await publication.publish_operator_action(
                    action_id=f"interaction-operator-action:{session_id}:{result.turn_id}:{timestamp}",
                    actor_ref=actor, input_class=OperatorInputClass.COMMAND,
                    target_ref=target_ref, timestamp=timestamp,
                    precondition_basis_ref=f"{target_ref}:cancel_requested", result="accepted_cancel",
                    command_class=OperatorCommandClass.CANCEL_RUN,
                    affected_transition_refs=[f"interaction-turn:{result.turn_id}:interrupted"],
                    affected_resource_refs=[f"interaction-session:{session_id}",
                                            f"interaction-turn:{result.turn_id}"],
                    receipt_refs=[f"interaction-cancel:{result.turn_id}"],
                )
            return {"ok": True, "target": target}

        return await run_owned_io(operation, label="interaction-cancellation", preserve_failure=True)
