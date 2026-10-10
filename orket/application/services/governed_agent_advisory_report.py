"""Report-only completion verification for governed agent workloads.

A workload opts in by requiring ``ADVISORY_REPORT_VERIFICATION_FEATURE``. Its
iteration result then completes only as a structurally valid advisory report:
a JSON ``advisory_proposal`` with a non-empty ``report`` and ``source_refs``
drawn from the request's own authoritative context, and no effect proposals.

Verification is structural and provenance-bound. It does not judge whether
the report is correct; a report remains model-assisted advice for a human.
Workloads that do not require the feature keep the ticket-report fixture
verifier unchanged.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from orket.application.services.governed_agent_iteration_policy import GovernedAgentVerificationObservation
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult, canonical_digest_sha256

ADVISORY_REPORT_VERIFICATION_FEATURE = "agent_advisory_report_verification.v1"
MAX_REPORT_CHARACTERS = 60_000

ADVISORY_REPORT_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["report", "source_refs"],
    "properties": {
        "report": {"type": "string", "minLength": 1, "maxLength": MAX_REPORT_CHARACTERS},
        "source_refs": {"type": "array", "items": {"type": "string"}, "minItems": 1, "uniqueItems": True},
    },
}


class AdvisoryReportVerifier:
    """Admit one returned, effect-free report whose sources the request supplied."""

    async def verify(
        self,
        *,
        request: AgentIterationRequest,
        result: AgentIterationResult,
    ) -> GovernedAgentVerificationObservation:
        report = _admissible_report(request, result)
        satisfied = report is not None
        ordinal = request.identity.iteration_ordinal
        return GovernedAgentVerificationObservation(
            verifier_id="advisory-report-verifier",
            verifier_version="v1",
            output_admissible=satisfied,
            objective_satisfied=satisfied,
            evidence_sufficient=satisfied,
            evidence_ref=f"agent-advisory-report-verification:{request.identity.run_id}:{ordinal:08d}",
            authoritative_result_ref=f"agent-result:{request.identity.invocation_id}" if satisfied else None,
            progress_projection_digest=(
                "sha256:" + canonical_digest_sha256(report) if report is not None else None
            ),
        )


def requires_advisory_report_verification(agent_declaration: Mapping[str, Any]) -> bool:
    return ADVISORY_REPORT_VERIFICATION_FEATURE in (agent_declaration.get("required_host_features") or ())


def is_advisory_report_schema(schema: object) -> bool:
    return isinstance(schema, Mapping) and list(schema.get("required") or ()) == ["report", "source_refs"]


def fixture_advisory_report(source: Any) -> dict[str, Any]:
    """Deterministic offline response for the advisory-report schema; never live proof."""
    if not isinstance(source, Mapping) or not isinstance(source.get("sources"), list):
        raise ValueError("E_AGENT_FIXTURE_ADVISORY_INPUT_INVALID")
    refs = [str(item["reference"]) for item in source["sources"] if isinstance(item, Mapping) and item.get("reference")]
    if not refs:
        raise ValueError("E_AGENT_FIXTURE_ADVISORY_INPUT_INVALID")
    return {"report": f"Deterministic fixture report over {len(refs)} source(s).", "source_refs": refs}


def _admissible_report(request: AgentIterationRequest, result: AgentIterationResult) -> dict[str, Any] | None:
    if result.invocation_status != "returned" or result.effect_proposals or result.advisory_proposal is None:
        return None
    try:
        report = json.loads(result.advisory_proposal)
    except json.JSONDecodeError:
        return None
    if not isinstance(report, dict) or set(report) != {"report", "source_refs"}:
        return None
    text, refs = report["report"], report["source_refs"]
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_REPORT_CHARACTERS:
        return None
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs):
        return None
    if len(set(refs)) != len(refs) or not set(refs).issubset(request.authoritative_context_refs):
        return None
    return report
