"""A report-only repository audit as one host-governed agent iteration.

The host supplies the task (``objective``) and a bounded repository snapshot
(``authoritative_context`` inputs). One brokered ``auditor`` model call turns
them into an advisory report; the workload proposes no effects. Completion is
decided by the host's advisory-report verifier, which the manifest requests
through ``agent_advisory_report_verification.v1``.
"""
from __future__ import annotations

from orket_extension_sdk import (
    AgentIterationResult,
    AgentModelCallRequest,
    AgentModelMessage,
    AgentUsage,
    AgentWorkloadContext,
    canonical_json,
)

_INSTRUCTION = (
    "You are auditing a software repository. The objective describes the task. "
    "Each entry in sources is a file or listing from the repository or its conventions, "
    "with a reference. Base every statement only on those sources and say plainly what "
    "they do not show. Return only a JSON object with report (the full answer, as "
    "Markdown text) and source_refs (the references you relied on, chosen from the "
    "supplied sources). Keep report under {words} words: the most significant findings "
    "first. If the objective asks for a closing summary line, end report with it."
)
_DEFAULT_REPORT_WORDS = 250

_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["report", "source_refs"],
    "properties": {
        # Kept minimal on purpose: a maxLength/uniqueItems grammar crashed the Ollama
        # runner on a 2 GB GPU. The host's advisory-report verifier still enforces
        # the length bound, uniqueness and provenance of source_refs.
        "report": {"type": "string", "minLength": 1},
        "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    },
}


class RepositoryAuditAgent:
    async def run(self, context: AgentWorkloadContext) -> AgentIterationResult:
        request = context.request
        await context.progress.report(summary="Auditing the supplied repository snapshot.")
        content = canonical_json(_audit_input(request))
        receipts = []
        repairs = 0
        call = await context.model.call(_call_request(context, "auditor-1", content, repair=False))
        receipts.append(call.receipt)
        if call.receipt.status != "returned" and request.remaining_iteration_budget.repair_attempts > 0:
            call = await context.model.call(_call_request(context, "auditor-repair-1", content, repair=True))
            receipts.append(call.receipt)
            repairs = 1
        returned = call.receipt.status == "returned"
        return AgentIterationResult(
            identity=request.identity,
            invocation_status="returned" if returned else "failed",
            observations=(
                ("The auditor returned a host-receipted advisory report.",) if returned
                else ("The auditor model call did not return a valid report.",)
            ),
            advisory_proposal=canonical_json(call.response.thaw()) if returned else None,
            advisory_proposal_ref=None,
            effect_proposals=(),
            progress_claims=(),
            completion_recommendation="complete" if returned else "stop",
            completion_evidence_refs=(),
            handoff_proposals=(),
            memory_write_proposals=(),
            model_receipts=tuple(receipts),
            usage=_usage(receipts, repairs),
            normalized_reason=None if returned else (call.normalized_reason or "model_call_failed"),
        )


def _audit_input(request) -> dict:
    objective = None
    sources = []
    for item in request.materialized_inputs:
        if item.kind == "objective":
            objective = item.content.thaw()
        elif item.kind == "authoritative_context":
            sources.append({"reference": item.reference, "content": item.content.thaw()})
    return {"objective": objective, "sources": sources}


def _call_request(context, call_id: str, content: str, *, repair: bool) -> AgentModelCallRequest:
    profile = next(item for item in context.request.model_profiles if item.role == "auditor")
    config = context.request.extension_config.thaw()
    words = config.get("report_word_limit") if isinstance(config, dict) else None
    instruction = _INSTRUCTION.format(words=words if isinstance(words, int) and words > 0 else _DEFAULT_REPORT_WORDS)
    if repair:
        instruction += " A prior response failed validation; return the JSON object exactly as specified."
    return AgentModelCallRequest(
        identity=context.request.identity,
        call_id=call_id,
        role="auditor",
        profile_ref=profile.profile_ref,
        capability_class=profile.capability_class,
        messages=(AgentModelMessage(role="system", content=instruction), AgentModelMessage(role="user", content=content)),
        response_mode="json",
        response_schema=_RESPONSE_SCHEMA,
        max_input_tokens=profile.max_input_tokens,
        max_output_tokens=profile.max_output_tokens,
        timeout_ms=profile.timeout_ms,
        temperature=0,
        seed=None,
        streaming_preference="disabled",
        tool_descriptions=(),
        stop_sequences=(),
    )


def _usage(receipts, repairs: int) -> AgentUsage:
    unknown = any(receipt.usage_posture == "unknown" for receipt in receipts)
    estimated = any(receipt.usage_posture == "estimated" for receipt in receipts)
    posture = "unknown" if unknown else "estimated" if estimated else "measured"
    return AgentUsage(
        model_calls=len(receipts),
        usage_posture=posture,
        input_tokens=None if unknown else sum(receipt.input_tokens or 0 for receipt in receipts),
        output_tokens=None if unknown else sum(receipt.output_tokens or 0 for receipt in receipts),
        estimate_source="combined_host_receipts" if posture == "estimated" else None,
        charged_input_tokens=sum(receipt.charged_input_tokens for receipt in receipts),
        charged_output_tokens=sum(receipt.charged_output_tokens for receipt in receipts),
        effect_proposals=0,
        output_bytes=0,
        artifact_bytes=0,
        repair_attempts=repairs,
    )


__all__ = ["RepositoryAuditAgent"]
