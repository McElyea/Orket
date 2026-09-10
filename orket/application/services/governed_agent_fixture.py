from __future__ import annotations

import json
from typing import Any

from orket.application.services.governed_agent_broker_service import (
    GovernedAgentModelObservation,
    GovernedAgentResolvedModelProfile,
)
from orket.application.services.governed_agent_iteration_policy import (
    GovernedAgentVerificationObservation,
)
from orket_extension_sdk import (
    AgentIterationRequest,
    AgentIterationResult,
    AgentModelCallRequest,
    canonical_digest_sha256,
)
from orket_extension_sdk.agent_testing import ticket_report_fixture


class DeterministicAgentModelProvider:
    """Explicit offline fixture provider; it is never live-model proof."""

    async def call(
        self,
        *,
        request: AgentModelCallRequest,
        profile: GovernedAgentResolvedModelProfile,
    ) -> GovernedAgentModelObservation:
        source = json.loads(request.messages[-1].content)
        response = _fixture_role_response(request.role, source)
        return GovernedAgentModelObservation(
            response=response,
            usage_posture="estimated",
            input_tokens=min(_token_estimate(request.messages[-1].content), request.max_input_tokens),
            output_tokens=min(_token_estimate(json.dumps(response)), request.max_output_tokens),
            estimate_source="utf8_bytes_div4_v1",
            latency_ms=0,
            finish_reason="fixture",
        )


class SecondIterationDeterministicVerifier:
    """Fixture verifier that admits completion only at the second bounded iteration."""

    async def verify(
        self,
        *,
        request: AgentIterationRequest,
        result: AgentIterationResult,
    ) -> GovernedAgentVerificationObservation:
        ordinal = request.identity.iteration_ordinal
        proposal = json.loads(result.advisory_proposal) if result.advisory_proposal is not None else None
        fixture = ticket_report_fixture(_fixture_case(request.objective_ref))
        expected = fixture["expected_report"]
        admissible = _valid_ticket_report(proposal, fixture, request)
        report_matches = admissible and proposal["source_refs"] == expected["source_refs"]
        satisfied = ordinal >= 2 and result.invocation_status == "returned" and report_matches
        return GovernedAgentVerificationObservation(
            verifier_id="deterministic-agent-fixture-verifier",
            verifier_version="v2",
            output_admissible=result.invocation_status == "returned" and admissible,
            objective_satisfied=satisfied,
            evidence_sufficient=satisfied,
            evidence_ref=f"agent-fixture-verification:{request.identity.run_id}:{ordinal:08d}",
            authoritative_result_ref=(
                f"agent-result:{request.identity.invocation_id}" if satisfied else None
            ),
            progress_projection_digest=("sha256:" + canonical_digest_sha256({
                "counts": proposal["counts"], "source_refs": proposal["source_refs"],
            }) if admissible else None),
        )


def _valid_ticket_report(proposal: Any, fixture: dict[str, Any], request: AgentIterationRequest) -> bool:
    if not isinstance(proposal, dict) or not isinstance(proposal.get("source_refs"), list):
        return False
    refs = proposal["source_refs"]
    if not refs or any(not isinstance(ref, str) for ref in refs) or len(set(refs)) != len(refs):
        return False
    available = set(request.authoritative_context_refs)
    for item in request.materialized_inputs:
        if item.kind == "authoritative_context" and item.content.thaw() != fixture["batches"].get(item.reference):
            return False
        if item.kind == "prior_verified_output":
            prior = item.content.thaw().get("advisory_proposal")
            if isinstance(prior, str):
                available.update(json.loads(prior).get("source_refs", []))
    if set(refs) != available or not available.issubset(fixture["batches"]):
        return False
    counts: dict[str, int] = {}
    for ref in refs:
        for ticket in fixture["batches"][ref]:
            counts[ticket["status"]] = counts.get(ticket["status"], 0) + 1
    return proposal.get("counts") == counts


def _fixture_case(objective_ref: str) -> str:
    cases = {"objective:ticket-report": "mixed", "objective:ticket-report:all-open": "all-open",
             "objective:ticket-report:empty-first": "empty-first"}
    if objective_ref not in cases:
        raise ValueError("E_AGENT_FIXTURE_OBJECTIVE_UNSUPPORTED")
    return cases[objective_ref]


def _fixture_role_response(role: str, source: Any) -> dict[str, Any]:
    if role == "planner":
        counts: dict[str, int] = {}
        refs: list[str] = []
        prior = [item for item in source if item.get("kind") == "prior_verified_output"]
        if prior:
            report = prior[-1]["content"]
            counts = dict(report["counts"])
            refs = list(report["source_refs"])
        for item in source if isinstance(source, list) else ():
            if not isinstance(item, dict) or item.get("kind") != "authoritative_context":
                continue
            if item["reference"] in refs:
                continue
            refs.append(str(item["reference"]))
            for ticket in item.get("content", []):
                status = str(ticket["status"])
                counts[status] = counts.get(status, 0) + 1
        return {"counts": dict(sorted(counts.items())), "source_refs": refs, "next_action": "render_report"}
    if isinstance(source, dict):
        response = {"counts": source.get("counts", {}), "source_refs": source.get("source_refs", [])}
        if role == "critic":
            response["critic"] = {"accepted": True, "defects": []}
        return response
    raise ValueError("E_AGENT_FIXTURE_ROLE_INPUT_INVALID")


def _token_estimate(value: str) -> int:
    return max(1, (len(value.encode("utf-8")) + 3) // 4)
