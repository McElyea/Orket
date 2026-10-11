"""Host-owned acceptance of a bounded advisory report, independent of its author."""
from __future__ import annotations

import json

from jsonschema import Draft202012Validator

from orket.application.services.governed_agent_iteration_policy import GovernedAgentVerificationObservation
from orket_extension_sdk import (
    AgentIterationRequest,
    AgentIterationResult,
    GovernedAgentSubmission,
    canonical_digest_sha256,
)


class StructuredReportVerifier:
    """Validate report delivery and input references; never certify the findings as true."""

    def __init__(self, submission: GovernedAgentSubmission) -> None:
        if submission.verifier_class != "structured_report.v1":
            raise ValueError("E_AGENT_TASK_VERIFIER_UNSUPPORTED")
        config = submission.verifier_config.thaw()
        sections = config.get("required_sections") if isinstance(config, dict) else None
        if (not isinstance(config, dict) or set(config) != {"required_sections"}
                or not isinstance(sections, list) or not 1 <= len(sections) <= 32
                or any(not isinstance(name, str) or not name.strip() or len(name) > 128 for name in sections)
                or len(set(sections)) != len(sections)):
            raise ValueError("E_AGENT_TASK_VERIFIER_CONFIG_INVALID")
        self._context_refs = frozenset(submission.initial_context_refs)
        self._identity = "sha256:" + canonical_digest_sha256({
            "class": submission.verifier_class, "config": config, "context_refs": sorted(self._context_refs),
        })
        self._validator = Draft202012Validator({
            "type": "object", "additionalProperties": False,
            "required": ["sections", "source_refs", "limitations", "advisory"],
            "properties": {
                "sections": {"type": "object", "additionalProperties": False, "required": sections,
                             "properties": {name: {"type": "string", "minLength": 1, "maxLength": 32768}
                                            for name in sections}},
                "source_refs": {"type": "array", "uniqueItems": True, "maxItems": 256,
                                "items": {"type": "string"}},
                "limitations": {"type": "array", "maxItems": 128,
                               "items": {"type": "string", "minLength": 1, "maxLength": 2048}},
                "advisory": {"const": True},
            },
        })

    async def verify(self, *, request: AgentIterationRequest,
                     result: AgentIterationResult) -> GovernedAgentVerificationObservation:
        try:
            report = json.loads(result.advisory_proposal) if result.advisory_proposal is not None else None
        except (json.JSONDecodeError, RecursionError):
            report = None
        valid = (result.invocation_status == "returned" and isinstance(report, dict) and self._validator.is_valid(report)
                 and set(report["source_refs"]) == self._context_refs
                 and set(request.authoritative_context_refs) == self._context_refs
                 and all(text.strip() for text in report["sections"].values())
                 and not result.effect_proposals and not result.memory_write_proposals
                 and not result.handoff_proposals
                 and all(receipt.status == "returned" and not receipt.truncated for receipt in result.model_receipts))
        return GovernedAgentVerificationObservation(
            verifier_id="structured_report", verifier_version="v1", output_admissible=valid,
            objective_satisfied=valid, evidence_sufficient=valid,
            evidence_ref=f"agent-report-verification:{self._identity}:{request.identity.invocation_id}",
            authoritative_result_ref=f"agent-result:{request.identity.invocation_id}" if valid else None,
            progress_projection_digest="sha256:" + canonical_digest_sha256(report) if valid else None,
        )
