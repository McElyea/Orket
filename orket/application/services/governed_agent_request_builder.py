from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from orket_extension_sdk import AgentIterationRequest, AgentIterationResult, canonical_digest_sha256, canonical_json


def build_next_agent_iteration_request(
    *,
    current_request: AgentIterationRequest,
    accepted_result: AgentIterationResult,
    next_lease_expires_at_utc: str,
    verification_evidence_ref: str,
) -> AgentIterationRequest:
    payload = deepcopy(current_request.to_wire())
    result_payload = accepted_result.to_wire()
    next_ordinal = current_request.identity.iteration_ordinal + 1
    result_ref = f"agent-result:{current_request.identity.invocation_id}"
    result_json = canonical_json(result_payload)
    payload["identity"] = {
        **payload["identity"],
        "iteration_ordinal": next_ordinal,
        "step_id": f"agent-step:{current_request.identity.run_id}:{next_ordinal:08d}",
        "trace_id": f"agent-trace:{current_request.identity.run_id}:{next_ordinal:08d}",
        "invocation_id": f"agent-invocation:{current_request.identity.run_id}:{next_ordinal:08d}",
    }
    payload["prior_verified_output_refs"] = [*payload["prior_verified_output_refs"], result_ref]
    payload["materialized_inputs"] = [
        *payload["materialized_inputs"],
        {
            "reference": result_ref,
            "kind": "prior_verified_output",
            "media_type": "application/json",
            "encoding": "json",
            "digest": _digest(result_payload),
            "encoded_bytes": len(result_json.encode("utf-8")),
            "content": result_payload,
            "provenance_refs": [verification_evidence_ref],
        },
    ]
    remaining_run = _remaining_run_budget(
        current_request.to_wire()["remaining_run_budget"],
        result_payload,
        next_ordinal,
        current_request.identity.run_id,
    )
    payload["remaining_run_budget"] = remaining_run
    payload["remaining_iteration_budget"] = _next_iteration_budget(
        current_request.to_wire()["remaining_iteration_budget"],
        remaining_run,
        next_ordinal,
        current_request.identity.run_id,
    )
    payload["lease_expires_at_utc"] = next_lease_expires_at_utc
    return AgentIterationRequest.from_wire(payload)


def _remaining_run_budget(
    budget: dict[str, Any],
    result: dict[str, Any],
    next_ordinal: int,
    run_id: str,
) -> dict[str, Any]:
    remaining = deepcopy(budget)
    usage = result["usage"]
    decrements = {
        "iterations": 1,
        "model_calls": int(usage["model_calls"]),
        "input_tokens": int(usage["charged_input_tokens"]),
        "output_tokens": int(usage["charged_output_tokens"]),
        "effect_proposals": int(usage["effect_proposals"]),
        "output_bytes": int(usage["output_bytes"]),
        "artifact_bytes": int(usage["artifact_bytes"]),
        "repair_attempts": int(usage["repair_attempts"]),
    }
    for field, decrement in decrements.items():
        remaining[field] = max(0, int(remaining[field]) - decrement)
    remaining["per_role_model_calls"] = _subtract_role_calls(
        remaining["per_role_model_calls"],
        result["model_receipts"],
    )
    remaining["per_capability_effects"] = _subtract_effect_calls(
        remaining["per_capability_effects"],
        result["effect_proposals"],
    )
    remaining["snapshot_ref"] = f"agent-budget:{run_id}:run:{next_ordinal:08d}"
    remaining["snapshot_digest"] = _snapshot_digest(remaining)
    return remaining


def _next_iteration_budget(
    iteration_budget: dict[str, Any],
    run_budget: dict[str, Any],
    next_ordinal: int,
    run_id: str,
) -> dict[str, Any]:
    issued = deepcopy(iteration_budget)
    scalar_fields = (
        "iterations",
        "wall_time_ms",
        "model_calls",
        "input_tokens",
        "output_tokens",
        "effect_proposals",
        "output_bytes",
        "artifact_bytes",
        "repair_attempts",
        "consecutive_failures",
        "repeated_states",
        "no_progress_iterations",
        "total_inference_concurrency",
    )
    for field in scalar_fields:
        issued[field] = min(int(issued[field]), int(run_budget[field]))
    issued["per_role_model_calls"] = _cap_counters(
        issued["per_role_model_calls"],
        run_budget["per_role_model_calls"],
        "role",
    )
    issued["per_role_inference_concurrency"] = _cap_counters(
        issued["per_role_inference_concurrency"],
        run_budget["per_role_inference_concurrency"],
        "role",
    )
    issued["per_capability_effects"] = _cap_counters(
        issued["per_capability_effects"],
        run_budget["per_capability_effects"],
        "capability",
    )
    issued["snapshot_ref"] = f"agent-budget:{run_id}:iteration:{next_ordinal:08d}"
    issued["snapshot_digest"] = _snapshot_digest(issued)
    return issued


def _subtract_role_calls(counters: list[dict[str, Any]], receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used: dict[str, int] = {}
    for receipt in receipts:
        role = str(receipt["role"])
        used[role] = used.get(role, 0) + 1
    return [
        {**counter, "count": max(0, int(counter["count"]) - used.get(str(counter["role"]), 0))}
        for counter in counters
    ]


def _subtract_effect_calls(
    counters: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    used: dict[str, int] = {}
    for proposal in proposals:
        capability = str(proposal["capability"])
        used[capability] = used.get(capability, 0) + 1
    return [
        {
            **counter,
            "count": max(0, int(counter["count"]) - used.get(str(counter["capability"]), 0)),
        }
        for counter in counters
    ]


def _cap_counters(
    issued: list[dict[str, Any]],
    remaining: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    limits = {str(item[key]): int(item["count"]) for item in remaining}
    return [
        {**item, "count": min(int(item["count"]), limits.get(str(item[key]), 0))}
        for item in issued
    ]


def _snapshot_digest(snapshot: dict[str, Any]) -> str:
    return _digest({key: value for key, value in snapshot.items() if key != "snapshot_digest"})


def _digest(payload: Any) -> str:
    return "sha256:" + cast(str, canonical_digest_sha256(payload))
