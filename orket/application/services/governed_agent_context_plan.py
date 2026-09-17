from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.core.contracts import RunRecord
from orket.core.contracts.governed_agent_wake_records import GovernedAgentWakeRepository
from orket.core.domain.control_plane_run_authority import same_run_admission
from orket_extension_sdk import AgentIterationRequest, canonical_digest_sha256


def validate_continuation_inputs(
    request: AgentIterationRequest, value: object,
) -> dict[str, list[dict[str, Any]]]:
    """Validate host-only, ordinal-indexed context without delivering future inputs."""
    if value is None:
        return {}
    if not isinstance(value, Mapping) or len(value) > 100:
        raise ValueError("E_AGENT_CONTINUATION_INPUTS_INVALID")
    plan: dict[str, list[dict[str, Any]]] = {}
    identities = {item.reference: item.digest for item in request.materialized_inputs}
    for ordinal, inputs in value.items():
        if not isinstance(ordinal, str) or not ordinal.isascii() or not ordinal.isdecimal():
            raise ValueError("E_AGENT_CONTINUATION_ORDINAL_INVALID")
        if str(int(ordinal)) != ordinal or not 2 <= int(ordinal) <= 100:
            raise ValueError("E_AGENT_CONTINUATION_ORDINAL_INVALID")
        if int(ordinal) >= request.identity.iteration_ordinal + request.remaining_run_budget.iterations:
            raise ValueError("E_AGENT_CONTINUATION_EXCEEDS_RUN_BUDGET")
        if not isinstance(inputs, list) or not inputs:
            raise ValueError("E_AGENT_CONTINUATION_CONTEXT_REQUIRED")
        payload = replace_authoritative_context(request.to_wire(), inputs)
        validated = AgentIterationRequest.from_wire(payload)
        plan[ordinal] = [item for item in validated.to_wire()["materialized_inputs"]
                         if item["kind"] == "authoritative_context"]
        for item in plan[ordinal]:
            previous = identities.setdefault(item["reference"], item["digest"])
            if previous != item["digest"]:
                raise ValueError("E_AGENT_CONTINUATION_REFERENCE_DRIFT")
    return plan


def replace_authoritative_context(payload: dict[str, Any], inputs: list[dict[str, Any]]) -> dict[str, Any]:
    if any(not isinstance(item, dict) or item.get("kind") != "authoritative_context"
           or not isinstance(item.get("reference"), str) for item in inputs):
        raise ValueError("E_AGENT_CONTINUATION_KIND_INVALID")
    return {
        **payload,
        "authoritative_context_refs": [item["reference"] for item in inputs],
        "materialized_inputs": [item for item in payload["materialized_inputs"]
                                if item["kind"] != "authoritative_context"] + inputs,
    }


def bind_continuation_configuration(configuration_digest: str, plan: Mapping[str, Any]) -> str:
    if not plan:
        return configuration_digest
    return "sha256:" + canonical_digest_sha256({
        "configuration_digest": configuration_digest, "continuation_inputs": dict(plan),
    })


async def retained_continuation_inputs(
    wakes: GovernedAgentWakeRepository, run_id: str,
) -> dict[str, list[dict[str, Any]]]:
    origins = [wake for wake in await wakes.list_wakes(target_run_id=run_id)
               if wake.state == "completed" and wake.payload["request"]["identity"]["iteration_ordinal"] == 1]
    plans = [validate_continuation_inputs(
        AgentIterationRequest.from_wire(dict(wake.payload["request"])),
        wake.payload.get("continuation_inputs"),
    ) for wake in origins]
    if any(plan != plans[0] for plan in plans):
        raise ValueError("E_AGENT_CONTINUATION_ORIGIN_CONFLICT")
    return plans[0] if plans else {}


def same_run_authority(existing: RunRecord, expected: RunRecord) -> bool:
    # Reentry observes a new time; it retains the original admission timestamp.
    retained_time = expected.model_copy(update={"creation_timestamp": existing.creation_timestamp})
    return same_run_admission(existing, retained_time) and existing.current_attempt_id == expected.current_attempt_id
