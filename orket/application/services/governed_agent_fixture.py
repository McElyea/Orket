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
from orket_extension_sdk import AgentIterationRequest, AgentIterationResult, AgentModelCallRequest
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
        expected = ticket_report_fixture()["expected_report"]
        report_matches = isinstance(proposal, dict) and {
            "counts": proposal.get("counts"),
            "source_refs": proposal.get("source_refs"),
        } == expected
        satisfied = ordinal >= 2 and result.invocation_status == "returned" and report_matches
        return GovernedAgentVerificationObservation(
            verifier_id="deterministic-agent-fixture-verifier",
            verifier_version="v1",
            output_admissible=result.invocation_status == "returned",
            objective_satisfied=satisfied,
            evidence_sufficient=satisfied,
            evidence_ref=f"agent-fixture-verification:{request.identity.run_id}:{ordinal:08d}",
            authoritative_result_ref=(
                f"agent-fixture-result:{request.identity.run_id}" if satisfied else None
            ),
        )


def _fixture_role_response(role: str, source: Any) -> dict[str, Any]:
    if role == "planner":
        counts: dict[str, int] = {}
        refs: list[str] = []
        for item in source if isinstance(source, list) else ():
            if not isinstance(item, dict) or item.get("kind") != "authoritative_context":
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
