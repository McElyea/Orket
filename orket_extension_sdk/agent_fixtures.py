from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from typing import Any

from .controller import canonical_json


def prefixed_digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def prefixed_digest(value: Any) -> str:
    return prefixed_digest_bytes(canonical_json(value).encode("utf-8"))


def agent_identity() -> dict[str, Any]:
    return {
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "iteration_ordinal": 1,
        "step_id": "step-1",
        "trace_id": "trace-1",
        "invocation_id": "invocation-1",
        "fencing_generation": 1,
    }


def agent_budget(scope: str = "iteration_remaining") -> dict[str, Any]:
    values: dict[str, Any] = {
        "schema_version": "agent_budget_snapshot.v1",
        "snapshot_ref": f"budget:{scope}:1",
        "scope": scope,
        "iterations": 2,
        "wall_time_ms": 30_000,
        "model_calls": 3,
        "per_role_model_calls": [{"role": "planner", "count": 3}],
        "input_tokens": 4_096,
        "output_tokens": 2_048,
        "effect_proposals": 2,
        "per_capability_effects": [{"capability": "write_file", "count": 1}],
        "output_bytes": 262_144,
        "artifact_bytes": 262_144,
        "repair_attempts": 1,
        "consecutive_failures": 2,
        "repeated_states": 2,
        "no_progress_iterations": 2,
        "total_inference_concurrency": 1,
        "per_role_inference_concurrency": [{"role": "planner", "count": 1}],
    }
    values["snapshot_digest"] = prefixed_digest(values)
    return values


def agent_model_profile_request() -> dict[str, Any]:
    return {
        "object_type": "agent_model_profile_request",
        "schema_version": "agent_model_profile_request.v1",
        "role": "planner",
        "profile_ref": "local.planner",
        "max_input_tokens": 4_096,
        "max_output_tokens": 1_024,
        "timeout_ms": 15_000,
        "response_mode": "json",
        "streaming_preference": "disabled",
    }


def agent_model_call_request() -> dict[str, Any]:
    return {
        "object_type": "agent_model_call_request",
        "schema_version": "agent_model_call_request.v1",
        "identity": agent_identity(),
        "call_id": "call-1",
        "role": "planner",
        "profile_ref": "local.planner",
        "messages": [{"role": "user", "content": "Count tickets by status."}],
        "response_mode": "json",
        "response_schema": {
            "type": "object",
            "required": ["counts"],
            "properties": {"counts": {"type": "object"}},
        },
        "max_input_tokens": 4_096,
        "max_output_tokens": 1_024,
        "timeout_ms": 15_000,
        "temperature": 0,
        "seed": 7,
        "streaming_preference": "disabled",
        "tool_descriptions": [],
        "stop_sequences": [],
    }


def agent_model_use_receipt(*, usage_posture: str = "measured") -> dict[str, Any]:
    measured = usage_posture in {"measured", "estimated"}
    return {
        "object_type": "agent_model_use_receipt",
        "schema_version": "agent_model_use_receipt.v2",
        "identity": agent_identity(),
        "call_id": "call-1",
        "role": "planner",
        "requested_profile_ref": "local.planner",
        "resolved_profile_ref": "local.planner.ollama",
        "provider": "ollama",
        "provider_version": "0.11.0",
        "model": "qwen-local",
        "model_digest": "sha256:" + "a" * 64,
        "status": "returned",
        "usage_posture": usage_posture,
        "input_tokens": 128 if measured else None,
        "output_tokens": 64 if measured else None,
        "estimate_source": "host_tokenizer.v1" if usage_posture == "estimated" else None,
        "charged_input_tokens": 128,
        "charged_output_tokens": 64,
        "latency_ms": 42, "latency_posture": "reported",
        "finish_reason": "stop",
        "truncated": False,
        "substitution_posture": "requested",
    }


def agent_model_call_result() -> dict[str, Any]:
    response = {"counts": {"open": 2, "closed": 1}}
    return {
        "object_type": "agent_model_call_result",
        "schema_version": "agent_model_call_result.v1",
        "identity": agent_identity(),
        "call_id": "call-1",
        "role": "planner",
        "response": response,
        "response_digest": prefixed_digest(response),
        "receipt": agent_model_use_receipt(),
        "normalized_reason": None,
    }


def agent_memory_query_request() -> dict[str, Any]:
    return {
        "object_type": "agent_memory_query_request",
        "schema_version": "agent_memory_query_request.v1",
        "identity": agent_identity(),
        "call_id": "memory-call-1",
        "scope": "extension_private",
        "role": None,
        "query": "prior ticket counts",
        "max_items": 8,
        "max_content_bytes": 16_384,
    }


def agent_memory_query_result() -> dict[str, Any]:
    content = {"open": 1}
    return {
        "object_type": "agent_memory_query_result",
        "schema_version": "agent_memory_query_result.v1",
        "identity": agent_identity(),
        "call_id": "memory-call-1",
        "status": "returned",
        "entries": [
            {
                "reference": "memory:1",
                "content": content,
                "content_digest": prefixed_digest(content),
                "provenance_refs": ["artifact:batch-a"],
            }
        ],
        "normalized_reason": None,
    }


def agent_effect_proposal() -> dict[str, Any]:
    arguments = {"path": "report.md", "content_ref": "artifact:draft"}
    return {
        "object_type": "agent_effect_proposal",
        "schema_version": "agent_effect_proposal.v1",
        "identity": agent_identity(),
        "proposal_id": "proposal-1",
        "capability": "write_file",
        "intended_target": "workspace:report.md",
        "namespace": "workspace:issue-1",
        "arguments": arguments,
        "arguments_digest": prefixed_digest(arguments),
        "idempotency_key": "effect-run-1-step-1",
        "evidence_refs": ["artifact:draft"],
    }


def agent_progress() -> dict[str, Any]:
    return {
        "object_type": "agent_progress",
        "schema_version": "agent_progress.v1",
        "identity": agent_identity(),
        "sequence": 1,
        "summary": "Counted the first ticket batch.",
        "evidence_refs": ["artifact:draft"],
    }


def agent_usage(*, usage_posture: str = "measured") -> dict[str, Any]:
    measured = usage_posture in {"measured", "estimated"}
    return {
        "object_type": "agent_usage",
        "schema_version": "agent_usage.v1",
        "model_calls": 1,
        "usage_posture": usage_posture,
        "input_tokens": 128 if measured else None,
        "output_tokens": 64 if measured else None,
        "estimate_source": "host_tokenizer.v1" if usage_posture == "estimated" else None,
        "charged_input_tokens": 128,
        "charged_output_tokens": 64,
        "effect_proposals": 1,
        "output_bytes": 512,
        "artifact_bytes": 0,
        "repair_attempts": 0,
    }


def agent_cancellation(*, requested: bool = False) -> dict[str, Any]:
    return {
        "object_type": "agent_cancellation",
        "schema_version": "agent_cancellation.v1",
        "requested": requested,
        "cancellation_epoch": 1 if requested else 0,
        "reason": "operator_request" if requested else None,
    }


def _materialized(reference: str, kind: str, content: Any) -> dict[str, Any]:
    encoded = canonical_json(content).encode("utf-8")
    return {
        "reference": reference,
        "kind": kind,
        "media_type": "application/json",
        "encoding": "json",
        "digest": prefixed_digest_bytes(encoded),
        "encoded_bytes": len(encoded),
        "content": content,
        "provenance_refs": [f"provenance:{reference}"],
    }


def governed_agent_submission() -> dict[str, Any]:
    return {
        "object_type": "governed_agent_submission",
        "schema_version": "governed_agent_submission.v1",
        "objective_ref": "objective:report",
        "acceptance_ref": "acceptance:report-v1",
        "initial_context_refs": ["artifact:batch-a"],
        "extension_id": "example.agent",
        "workload_id": "governed-agent-loop",
        "agent_contract_version": "governed_agent_loop.v1",
        "allowed_capabilities": ["agent.iteration.v1", "write_file"],
        "namespace_scope": ["workspace:issue-1"],
        "policy_ref": "policy:agent-v1",
        "policy_digest": "sha256:" + "b" * 64,
        "policy_schema_version": "governed_agent_policy.v1",
        "run_budget": agent_budget("run_limit"),
        "iteration_budget": agent_budget("iteration_limit"),
        "verifier_class": "artifact_contract",
        "verifier_config": {"required_path": "report.md"},
        "requested_model_profiles": [agent_model_profile_request()],
        "recovery_posture": "fail_closed",
        "operator_ref": "operator:local",
    }


def agent_iteration_request() -> dict[str, Any]:
    return {
        "object_type": "agent_iteration_request",
        "schema_version": "agent_iteration_request.v1",
        "identity": agent_identity(),
        "objective_ref": "objective:report",
        "acceptance_ref": "acceptance:report-v1",
        "authoritative_context_refs": ["artifact:batch-a"],
        "prior_verified_output_refs": [],
        "materialized_inputs": [
            _materialized("objective:report", "objective", {"task": "Count tickets by status."}),
            _materialized("acceptance:report-v1", "acceptance", {"required": ["counts", "sources"]}),
            _materialized("artifact:batch-a", "authoritative_context", [{"status": "open"}]),
        ],
        "effect_receipts": [],
        "admitted_capabilities": ["agent.iteration.v1", "write_file", "memory.write"],
        "namespace_scope": ["workspace:issue-1"],
        "model_profiles": [agent_model_profile_request()],
        "policy_ref": "policy:agent-v1",
        "policy_digest": "sha256:" + "b" * 64,
        "remaining_run_budget": agent_budget("run_remaining"),
        "remaining_iteration_budget": agent_budget("iteration_remaining"),
        "deadline_utc": "2026-09-06T18:00:00Z",
        "lease_expires_at_utc": "2026-09-06T17:55:00Z",
        "cancellation": agent_cancellation(),
        "extension_config": {"roles": ["planner"]},
    }


def agent_iteration_result() -> dict[str, Any]:
    content = {"note": "batch A counted"}
    return {
        "object_type": "agent_iteration_result",
        "schema_version": "agent_iteration_result.v1",
        "identity": agent_identity(),
        "invocation_status": "returned",
        "observations": ["The source artifact was readable."],
        "advisory_proposal": "Write the first report section.",
        "effect_proposals": [agent_effect_proposal()],
        "progress_claims": [agent_progress()],
        "completion_recommendation": "continue",
        "completion_evidence_refs": [],
        "handoff_proposals": [],
        "memory_write_proposals": [
            {
                "identity": agent_identity(),
                "proposal_id": "memory-1",
                "scope": "extension_private",
                "role": None,
                "content": content,
                "content_digest": prefixed_digest(content),
                "provenance_refs": ["artifact:batch-a"],
                "evidence_refs": ["artifact:draft"],
            }
        ],
        "model_receipts": [agent_model_use_receipt()],
        "usage": agent_usage(),
        "normalized_reason": None,
    }


def agent_broker_frame() -> dict[str, Any]:
    return {
        "object_type": "agent_stdio_frame",
        "schema_version": "agent_stdio_frame.v1",
        "protocol_version": "agent_stdio_ipc.v1",
        "invocation_id": "invocation-1",
        "sequence": 1,
        "direction": "parent_to_child",
        "message_type": "bootstrap",
        "call_id": None,
        "operation": None,
        "payload": agent_iteration_request(),
    }


def valid_agent_wire_payloads() -> dict[str, dict[str, Any]]:
    payloads = [
        governed_agent_submission(),
        agent_iteration_request(),
        agent_iteration_result(),
        agent_model_profile_request(),
        agent_model_call_request(),
        agent_model_call_result(),
        agent_model_use_receipt(),
        agent_memory_query_request(),
        agent_memory_query_result(),
        agent_effect_proposal(),
        agent_progress(),
        agent_usage(),
        agent_cancellation(),
        agent_broker_frame(),
    ]
    return {str(payload["object_type"]): payload for payload in payloads}


def invalid_agent_wire_fixtures() -> dict[str, dict[str, Any]]:
    unknown_usage = agent_model_use_receipt(usage_posture="unknown")
    unknown_usage["input_tokens"] = 0
    known_usage = agent_model_use_receipt()
    known_usage["output_tokens"] = None
    missing_context = agent_iteration_request()
    missing_context["materialized_inputs"] = list(missing_context["materialized_inputs"])[:-1]
    forged_identity = agent_iteration_result()
    forged_identity["effect_proposals"][0]["identity"]["step_id"] = "step-forged"
    wrong_digest = agent_effect_proposal()
    wrong_digest["arguments_digest"] = "sha256:" + "0" * 64
    duplicate_roles = governed_agent_submission()
    duplicate_roles["requested_model_profiles"] = [
        agent_model_profile_request(),
        deepcopy(agent_model_profile_request()),
    ]
    invalid_base64 = _materialized("artifact:encoded", "authoritative_context", {"x": 1})
    invalid_base64.update(
        {
            "encoding": "base64",
            "content": base64.b64encode(b"valid").decode("ascii") + "!",
        }
    )
    encoded_request = agent_iteration_request()
    encoded_request["materialized_inputs"].append(invalid_base64)
    encoded_request["authoritative_context_refs"].append("artifact:encoded")
    return {
        "unknown_usage_with_invented_zero": unknown_usage,
        "known_usage_missing_count": known_usage,
        "unmaterialized_context_reference": missing_context,
        "nested_identity_mismatch": forged_identity,
        "arguments_digest_mismatch": wrong_digest,
        "duplicate_model_role": duplicate_roles,
        "invalid_base64_content": encoded_request,
    }
