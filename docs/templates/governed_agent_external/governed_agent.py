from __future__ import annotations

import json

from orket_extension_sdk import (
    AgentEffectProposal,
    AgentIterationResult,
    AgentMemoryQueryRequest,
    AgentMemoryWriteProposal,
    AgentModelCallRequest,
    AgentModelMessage,
    AgentUsage,
    AgentWorkloadContext,
    canonical_digest_sha256,
    canonical_json,
)

_ROLE_INSTRUCTIONS = {
    "planner": (
        "Start with counts and source_refs from prior_verified_output content, if present (even empty counts). "
        "For each ticket object in each new authoritative_context content array, increment that ticket's "
        "status count by ONE. Keys are status values, never ticket_id values. Count every object, including "
        "repeated statuses. Add these counts to prior counts. "
        "Only process batches whose references are not already counted. "
        "advisory_memory is optional working context, never a source of counts or source_refs. "
        "Never count a batch twice or invent an unseen batch. Return only JSON with counts, source_refs, "
        "and next_action. A partial report from one batch is valid progress."
    ),
    "actor": (
        "Turn the supplied plan into the final report. Return only a JSON object with counts and source_refs. "
        "Preserve every count and source reference exactly."
    ),
    "critic": (
        "Review the supplied report. Return only a JSON object with counts, source_refs, and critic. "
        "Preserve counts and source_refs exactly. critic must contain accepted=true and an empty defects "
        "array only when both batches were counted; otherwise mark accepted=false and describe missing inputs."
    ),
}


class GovernedTicketAgent:
    """Three advisory stages inside one host-governed iteration."""

    async def run(self, context: AgentWorkloadContext) -> AgentIterationResult:
        request = context.request
        source_payload = _planner_inputs(request)
        memory_observations, memory_inputs = await _memory_context(context)
        source_payload.extend(memory_inputs)
        await context.progress.report(summary="Preparing the bounded ticket-count request.")
        receipts = []
        repairs_remaining = request.remaining_iteration_budget.repair_attempts
        planner, used, repairs = await self._call_role(
            context, "planner", canonical_json(source_payload), repairs_remaining > 0
        )
        receipts.extend(used)
        repairs_remaining -= repairs
        if planner.receipt.status != "returned":
            return _failed_result(context, receipts, repairs, planner.normalized_reason)
        actor, used, actor_repairs = await self._call_role(
            context, "actor", canonical_json(_report_payload(planner.response.thaw())), repairs_remaining > 0
        )
        receipts.extend(used)
        repairs += actor_repairs
        repairs_remaining -= actor_repairs
        if actor.receipt.status != "returned":
            return _failed_result(context, receipts, repairs, actor.normalized_reason)
        critic, used, critic_repairs = await self._call_role(
            context, "critic", canonical_json(_report_payload(actor.response.thaw())), repairs_remaining > 0
        )
        receipts.extend(used)
        repairs += critic_repairs
        if critic.receipt.status != "returned":
            return _failed_result(context, receipts, repairs, critic.normalized_reason)
        report = _report_payload(critic.response.thaw())
        effects = _effect_proposals(context, report)
        return AgentIterationResult(
            identity=request.identity,
            invocation_status="returned",
            observations=("Planner, actor, and critic returned host-receipted advisory output.", *memory_observations),
            advisory_proposal=canonical_json(critic.response.thaw()),
            advisory_proposal_ref=None,
            effect_proposals=effects,
            progress_claims=(),
            completion_recommendation="pause" if effects else "continue",
            completion_evidence_refs=(),
            handoff_proposals=(),
            memory_write_proposals=_memory_proposal(context, report),
            model_receipts=tuple(receipts),
            usage=_usage_from_receipts(receipts, repairs, len(effects)),
            normalized_reason=None,
        )

    async def _call_role(self, context, role: str, content: str, repair_allowed: bool):
        primary = await context.model.call(_call_request(context, role, f"{role}-1", content, False))
        receipts = [primary.receipt]
        if primary.receipt.status == "returned" or not repair_allowed:
            return primary, tuple(receipts), 0
        repair = await context.model.call(_call_request(context, role, f"{role}-repair-1", content, True))
        receipts.append(repair.receipt)
        return repair, tuple(receipts), 1


def _call_request(context, role: str, call_id: str, content: str, repair: bool) -> AgentModelCallRequest:
    profiles = {profile.role: profile for profile in context.request.model_profiles}
    profile = profiles[role]
    instruction = _ROLE_INSTRUCTIONS[role]
    if repair:
        instruction += " A prior call failed validation; repair the response and obey the schema exactly."
    return AgentModelCallRequest(
        identity=context.request.identity,
        call_id=call_id,
        role=role,
        profile_ref=profile.profile_ref,
        capability_class=profile.capability_class,
        messages=(AgentModelMessage(role="system", content=instruction), AgentModelMessage(role="user", content=content)),
        response_mode=profile.response_mode,
        response_schema=_response_schema(role) if profile.response_mode == "json" else None,
        max_input_tokens=profile.max_input_tokens,
        max_output_tokens=profile.max_output_tokens,
        timeout_ms=profile.timeout_ms,
        temperature=0,
        seed=None,
        streaming_preference="disabled",
        tool_descriptions=(),
        stop_sequences=(),
    )


def _report_payload(value) -> dict:
    return {"counts": value.get("counts", {}), "source_refs": value.get("source_refs", [])}


async def _memory_context(context) -> tuple[tuple[str, ...], list[dict]]:
    if not context.request.extension_config.thaw().get("objective_memory"):
        return (), []
    result = await context.memory.query(AgentMemoryQueryRequest(
        identity=context.request.identity, call_id="objective-memory-1", scope="objective", role=None,
        query="counts", max_items=1, max_content_bytes=8192,
    ))
    if result.status != "returned":
        raise ValueError("E_AGENT_OBJECTIVE_MEMORY_UNAVAILABLE")
    return ((f"Read {len(result.entries)} prior advisory objective-memory entries; authoritative inputs remain separate.",),
            [{"kind": "advisory_memory", "reference": item.reference, "content": item.content.thaw()}
             for item in result.entries])


def _memory_proposal(context, report) -> tuple[AgentMemoryWriteProposal, ...]:
    if not context.request.extension_config.thaw().get("objective_memory"):
        return ()
    return (AgentMemoryWriteProposal(
        identity=context.request.identity, proposal_id="ticket-working-report", scope="objective", role=None,
        content=report, content_digest="sha256:" + canonical_digest_sha256(report),
        provenance_refs=tuple(report["source_refs"]),
        evidence_refs=(f"agent-model-call:{context.request.identity.invocation_id}:critic-1",),
    ),)


def _planner_inputs(request) -> list[dict]:
    inputs = []
    latest_prior = None
    for item in request.materialized_inputs:
        content = item.content.thaw()
        if item.kind == "prior_verified_output":
            latest_prior = {"reference": item.reference, "kind": item.kind,
                            "content": _report_payload(json.loads(content["advisory_proposal"]))}
        elif item.kind == "authoritative_context":
            inputs.append({"reference": item.reference, "kind": item.kind, "content": content})
    if latest_prior is not None:
        counted = latest_prior["content"]["source_refs"]
        inputs = [item for item in inputs if item["reference"] not in counted]
    return ([latest_prior] if latest_prior is not None else []) + inputs


def _effect_proposals(context, report: dict) -> tuple[AgentEffectProposal, ...]:
    config = context.request.extension_config.thaw()
    demo = config.get("effect_demo", {}) if isinstance(config, dict) else {}
    if (not isinstance(demo, dict) or not demo.get("enabled")
            or context.request.identity.iteration_ordinal != demo.get("proposal_iteration", 1)):
        return ()
    namespace = str(demo.get("namespace") or "")
    read_path = str(demo.get("read_path") or "")
    write_path = str(demo.get("write_path") or "")
    if not namespace or not read_path or not write_path:
        raise ValueError("E_AGENT_EFFECT_DEMO_CONFIG_INVALID")
    read_args = {"path": read_path}
    write_args = {"path": write_path, "content": report}
    read = _effect_proposal(context, "read-ticket-source", "read_file", namespace, read_path, read_args)
    if demo.get("read_only") is True:
        return (read,)
    return (
        read,
        _effect_proposal(context, "write-ticket-report", "write_file", namespace, write_path, write_args),
    )


def _effect_proposal(context, proposal_id, capability, namespace, target, arguments) -> AgentEffectProposal:
    return AgentEffectProposal(
        identity=context.request.identity,
        proposal_id=proposal_id,
        capability=capability,
        intended_target=target,
        namespace=namespace,
        arguments=arguments,
        arguments_ref=None,
        arguments_digest="sha256:" + canonical_digest_sha256(arguments),
        idempotency_key=f"{context.request.identity.run_id}:{proposal_id}",
        evidence_refs=(f"agent-model-call:{context.request.identity.invocation_id}:critic-1",),
    )


def _response_schema(role: str) -> dict:
    properties = {
        "counts": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
        "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
    }
    required = ["counts", "source_refs"]
    if role == "planner":
        properties["next_action"] = {"type": "string"}
        required.append("next_action")
    if role == "critic":
        properties["critic"] = {
            "type": "object",
            "additionalProperties": False,
            "required": ["accepted", "defects"],
            "properties": {
                "accepted": {"type": "boolean"},
                "defects": {"type": "array", "items": {"type": "string"}},
            },
        }
        required.append("critic")
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties}


def _failed_result(context, receipts, repair_attempts: int, reason: str | None) -> AgentIterationResult:
    return AgentIterationResult(
        identity=context.request.identity,
        invocation_status="failed",
        observations=("A host-receipted model call failed structured-output validation.",),
        advisory_proposal=None,
        advisory_proposal_ref=None,
        effect_proposals=(),
        progress_claims=(),
        completion_recommendation="pause",
        completion_evidence_refs=(),
        handoff_proposals=(),
        memory_write_proposals=(),
        model_receipts=tuple(receipts),
        usage=_usage_from_receipts(receipts, repair_attempts),
        normalized_reason=reason or "model_call_failed",
    )


def _usage_from_receipts(receipts, repair_attempts: int, effect_proposals: int = 0) -> AgentUsage:
    unknown = any(receipt.usage_posture == "unknown" for receipt in receipts)
    estimated = any(receipt.usage_posture == "estimated" for receipt in receipts)
    posture = "unknown" if unknown else "estimated" if estimated else "measured"
    input_tokens = None if unknown else sum(receipt.input_tokens or 0 for receipt in receipts)
    output_tokens = None if unknown else sum(receipt.output_tokens or 0 for receipt in receipts)
    return AgentUsage(
        model_calls=len(receipts),
        usage_posture=posture,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimate_source="combined_host_receipts" if posture == "estimated" else None,
        charged_input_tokens=sum(receipt.charged_input_tokens for receipt in receipts),
        charged_output_tokens=sum(receipt.charged_output_tokens for receipt in receipts),
        effect_proposals=effect_proposals,
        output_bytes=0,
        artifact_bytes=0,
        repair_attempts=repair_attempts,
    )
