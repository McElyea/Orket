from __future__ import annotations

from orket.application.services.governed_agent_broker_service import GovernedAgentMemoryObservation
from orket.application.services.governed_agent_ports import GovernedAgentIterationRepository
from orket_extension_sdk import AgentMemoryEntry, AgentMemoryQueryRequest


class GovernedAgentObjectiveMemory:
    """Run-scoped advisory memory projected from host-admitted, durable iteration results."""

    def __init__(self, iterations: GovernedAgentIterationRepository) -> None:
        self._iterations = iterations

    async def query(self, *, request: AgentMemoryQueryRequest) -> GovernedAgentMemoryObservation:
        if request.scope != "objective" or request.role is not None:
            raise ValueError("E_AGENT_MEMORY_SCOPE_UNADMITTED")
        current = await self._iterations.get_iteration_snapshot(invocation_id=request.identity.invocation_id)
        if current is None or current.request_payload["identity"] != request.identity.model_dump(mode="json"):
            raise ValueError("E_AGENT_MEMORY_INVOCATION_UNADMITTED")
        entries: list[AgentMemoryEntry] = []
        size = 0
        history = await self._iterations.list_iteration_snapshots(run_id=request.identity.run_id)
        for snapshot in reversed(history):
            if (snapshot.binding.iteration_ordinal >= request.identity.iteration_ordinal
                    or snapshot.binding.extension_digest != current.binding.extension_digest
                    or not snapshot.decision_inputs or not snapshot.decision_inputs.get("valid_recorded_result")
                    or not snapshot.decision_payload or snapshot.decision_payload.get("disposition") not in {"continue", "complete"}
                    or snapshot.result_payload is None):
                continue
            for proposal in snapshot.result_payload["memory_write_proposals"]:
                if proposal["scope"] != "objective" or proposal["role"] is not None:
                    continue
                entry = AgentMemoryEntry(
                    reference=f"agent-memory:{snapshot.binding.invocation_id}:{proposal['proposal_id']}",
                    content=proposal["content"], content_digest=proposal["content_digest"],
                    provenance_refs=(f"agent-result:{snapshot.binding.invocation_id}",
                                     f"agent-decision:{snapshot.binding.invocation_id}"),
                )
                encoded = entry.content.canonical.encode("utf-8")
                if request.query.casefold() not in entry.content.canonical.casefold():
                    continue
                if len(entries) >= request.max_items or size + len(encoded) > request.max_content_bytes:
                    return GovernedAgentMemoryObservation(tuple(entries))
                entries.append(entry)
                size += len(encoded)
        return GovernedAgentMemoryObservation(tuple(entries))
