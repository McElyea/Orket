from __future__ import annotations

import base64
import binascii
import hashlib
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .controller import canonical_json
from .schema import load_governed_agent_schema

MAX_AGENT_WIRE_BYTES = 1_048_576
MAX_AGENT_JSON_DEPTH = 32

_OBJECT_DEFS = {
    "governed_agent_submission": "submission",
    "agent_iteration_request": "iterationRequest",
    "agent_iteration_result": "iterationResult",
    "agent_model_profile_request": "modelProfileRequest",
    "agent_model_call_request": "modelCallRequest",
    "agent_model_call_result": "modelCallResult",
    "agent_model_use_receipt": "modelUseReceipt",
    "agent_memory_query_request": "memoryQueryRequest",
    "agent_memory_query_result": "memoryQueryResult",
    "agent_effect_proposal": "effectProposal",
    "agent_progress": "progress",
    "agent_usage": "usage",
    "agent_cancellation": "cancellation",
    "agent_stdio_frame": "brokerFrame",
}


def validate_governed_agent_payload(payload: Mapping[str, Any]) -> None:
    """Validate one public wire object against shape and host-independent semantics."""
    normalized = dict(payload)
    encoded = canonical_json(normalized).encode("utf-8")
    if len(encoded) > MAX_AGENT_WIRE_BYTES:
        raise ValueError("E_SDK_AGENT_ENCODED_BYTES_EXCEEDED")
    if _json_depth(normalized) > MAX_AGENT_JSON_DEPTH:
        raise ValueError("E_SDK_AGENT_NESTING_EXCEEDED")
    object_type = str(normalized.get("object_type") or "").strip()
    definition = _OBJECT_DEFS.get(object_type)
    if definition is None:
        raise ValueError(f"E_SDK_AGENT_OBJECT_TYPE_UNSUPPORTED: {object_type}")
    schema = load_governed_agent_schema()
    focused_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": f"#/$defs/{definition}",
    }
    try:
        Draft202012Validator(focused_schema).validate(normalized)
    except ValidationError as exc:
        raise ValueError(f"E_SDK_AGENT_SCHEMA_INVALID: {object_type}: {exc}") from exc
    _validate_semantics(normalized)


def validate_agent_iteration_result_against_request(
    *,
    request: Mapping[str, Any],
    result: Mapping[str, Any],
) -> None:
    """Apply host-owned invocation, scope, and remaining-budget checks."""
    validate_governed_agent_payload(request)
    validate_governed_agent_payload(result)
    if request["object_type"] != "agent_iteration_request":
        raise ValueError("E_HOST_AGENT_REQUEST_TYPE_INVALID")
    if result["object_type"] != "agent_iteration_result":
        raise ValueError("E_HOST_AGENT_RESULT_TYPE_INVALID")
    _require_same_identity(request["identity"], result["identity"], "result")
    admitted = set(request["admitted_capabilities"])
    namespaces = set(request["namespace_scope"])
    iteration_budget = request["remaining_iteration_budget"]
    effects = list(result["effect_proposals"])
    if len(effects) > iteration_budget["effect_proposals"]:
        raise ValueError("E_HOST_AGENT_EFFECT_BUDGET_EXCEEDED")
    per_capability = _counter_map(iteration_budget["per_capability_effects"], "capability")
    used_capabilities: dict[str, int] = {}
    for effect in effects:
        capability = str(effect["capability"])
        if capability not in admitted:
            raise ValueError(f"E_HOST_AGENT_CAPABILITY_UNDECLARED: {capability}")
        if effect["namespace"] not in namespaces:
            raise ValueError(f"E_HOST_AGENT_NAMESPACE_UNADMITTED: {effect['namespace']}")
        used_capabilities[capability] = used_capabilities.get(capability, 0) + 1
    for capability, used in used_capabilities.items():
        if used > per_capability.get(capability, 0):
            raise ValueError(f"E_HOST_AGENT_CAPABILITY_BUDGET_EXCEEDED: {capability}")
    for proposal in result["memory_write_proposals"]:
        if "memory.write" not in admitted:
            raise ValueError("E_HOST_AGENT_MEMORY_WRITE_UNDECLARED")
        if proposal["role"] is not None and proposal["role"] not in {item["role"] for item in request["model_profiles"]}:
            raise ValueError("E_HOST_AGENT_MEMORY_ROLE_UNADMITTED")
    _require_unique(result["memory_write_proposals"], "proposal_id", "E_HOST_AGENT_MEMORY_PROPOSAL_DUPLICATE")
    receipts = list(result["model_receipts"])
    if len(receipts) > iteration_budget["model_calls"]:
        raise ValueError("E_HOST_AGENT_MODEL_CALL_BUDGET_EXCEEDED")
    charged_input = sum(int(item["charged_input_tokens"]) for item in receipts)
    charged_output = sum(int(item["charged_output_tokens"]) for item in receipts)
    if charged_input > iteration_budget["input_tokens"]:
        raise ValueError("E_HOST_AGENT_INPUT_TOKEN_BUDGET_EXCEEDED")
    if charged_output > iteration_budget["output_tokens"]:
        raise ValueError("E_HOST_AGENT_OUTPUT_TOKEN_BUDGET_EXCEEDED")
    usage = result["usage"]
    if int(usage["model_calls"]) != len(receipts):
        raise ValueError("E_HOST_AGENT_USAGE_MODEL_CALL_MISMATCH")
    if int(usage["effect_proposals"]) != len(effects):
        raise ValueError("E_HOST_AGENT_USAGE_EFFECT_MISMATCH")
    if int(usage["charged_input_tokens"]) != charged_input:
        raise ValueError("E_HOST_AGENT_USAGE_INPUT_CHARGE_MISMATCH")
    if int(usage["charged_output_tokens"]) != charged_output:
        raise ValueError("E_HOST_AGENT_USAGE_OUTPUT_CHARGE_MISMATCH")
    result_bytes = len(canonical_json(dict(result)).encode("utf-8"))
    if result_bytes > iteration_budget["output_bytes"]:
        raise ValueError("E_HOST_AGENT_OUTPUT_BYTE_BUDGET_EXCEEDED")


def _validate_semantics(payload: dict[str, Any]) -> None:
    object_type = payload["object_type"]
    if object_type == "governed_agent_submission":
        _validate_submission(payload)
    elif object_type == "agent_iteration_request":
        _validate_iteration_request(payload)
    elif object_type == "agent_iteration_result":
        _validate_iteration_result(payload)
    elif object_type == "agent_model_call_result":
        _validate_model_call_result(payload)
    elif object_type == "agent_memory_query_result":
        _validate_memory_query_result(payload)
    elif object_type == "agent_effect_proposal":
        _validate_effect(payload)
    elif object_type == "agent_stdio_frame":
        _validate_frame(payload)
    if object_type in {"agent_model_use_receipt", "agent_usage"}:
        _validate_usage_posture(payload)
    identity = payload.get("identity")
    if isinstance(identity, dict):
        _validate_identity(identity)


def _validate_submission(payload: dict[str, Any]) -> None:
    _validate_budget(payload["run_budget"], "run_limit")
    _validate_budget(payload["iteration_budget"], "iteration_limit")
    _require_unique(payload["requested_model_profiles"], "role", "E_SDK_AGENT_ROLE_DUPLICATE")
    run_budget = payload["run_budget"]
    iteration_budget = payload["iteration_budget"]
    for field in _budget_scalar_fields():
        if int(iteration_budget[field]) > int(run_budget[field]):
            raise ValueError(f"E_SDK_AGENT_ITERATION_BUDGET_EXCEEDS_RUN: {field}")


def _validate_iteration_request(payload: dict[str, Any]) -> None:
    _validate_budget(payload["remaining_run_budget"], "run_remaining")
    _validate_budget(payload["remaining_iteration_budget"], "iteration_remaining")
    _require_unique(payload["model_profiles"], "role", "E_SDK_AGENT_ROLE_DUPLICATE")
    expected = {
        payload["objective_ref"]: "objective",
        payload["acceptance_ref"]: "acceptance",
        **{reference: "authoritative_context" for reference in payload["authoritative_context_refs"]},
        **{reference: "prior_verified_output" for reference in payload["prior_verified_output_refs"]},
    }
    materialized = {item["reference"]: item for item in payload["materialized_inputs"]}
    if len(materialized) != len(payload["materialized_inputs"]):
        raise ValueError("E_SDK_AGENT_MATERIALIZED_REFERENCE_DUPLICATE")
    if set(materialized) != set(expected):
        raise ValueError("E_SDK_AGENT_MATERIALIZED_REFERENCE_MISMATCH")
    for reference, kind in expected.items():
        item = materialized[reference]
        if item["kind"] != kind:
            raise ValueError(f"E_SDK_AGENT_MATERIALIZED_KIND_MISMATCH: {reference}")
        _validate_materialized_input(item)
    deadline = _parse_utc(payload["deadline_utc"])
    lease_expiry = _parse_utc(payload["lease_expires_at_utc"])
    if lease_expiry > deadline:
        raise ValueError("E_SDK_AGENT_LEASE_EXCEEDS_DEADLINE")


def _validate_iteration_result(payload: dict[str, Any]) -> None:
    identity = payload["identity"]
    for field in ("effect_proposals", "progress_claims", "handoff_proposals", "memory_write_proposals", "model_receipts"):
        for item in payload[field]:
            _require_same_identity(identity, item["identity"], field)
    _require_unique(payload["progress_claims"], "sequence", "E_SDK_AGENT_PROGRESS_SEQUENCE_DUPLICATE")
    _require_unique(payload["effect_proposals"], "proposal_id", "E_SDK_AGENT_EFFECT_ID_DUPLICATE")
    _require_unique(payload["model_receipts"], "call_id", "E_SDK_AGENT_CALL_ID_DUPLICATE")
    for effect in payload["effect_proposals"]:
        _validate_effect(effect)
    for memory in payload["memory_write_proposals"]:
        _require_digest(memory["content"], memory["content_digest"], "E_SDK_AGENT_MEMORY_DIGEST_MISMATCH")
    for receipt in payload["model_receipts"]:
        _validate_usage_posture(receipt)


def _validate_model_call_result(payload: dict[str, Any]) -> None:
    receipt = payload["receipt"]
    _require_same_identity(payload["identity"], receipt["identity"], "receipt")
    if payload["call_id"] != receipt["call_id"] or payload["role"] != receipt["role"]:
        raise ValueError("E_SDK_AGENT_MODEL_RESULT_RECEIPT_MISMATCH")
    response = payload["response"]
    response_digest = payload["response_digest"]
    if receipt["status"] == "returned":
        if response is None or response_digest is None:
            raise ValueError("E_SDK_AGENT_MODEL_RESPONSE_REQUIRED")
        if payload["normalized_reason"] is not None:
            raise ValueError("E_SDK_AGENT_RETURNED_MODEL_REASON_FORBIDDEN")
        _require_digest(response, response_digest, "E_SDK_AGENT_MODEL_RESPONSE_DIGEST_MISMATCH")
    else:
        if response is not None or response_digest is not None:
            raise ValueError("E_SDK_AGENT_FAILED_MODEL_RESPONSE_FORBIDDEN")
        if payload["normalized_reason"] is None:
            raise ValueError("E_SDK_AGENT_FAILED_MODEL_REASON_REQUIRED")


def _validate_memory_query_result(payload: dict[str, Any]) -> None:
    _require_unique(payload["entries"], "reference", "E_SDK_AGENT_MEMORY_REFERENCE_DUPLICATE")
    for entry in payload["entries"]:
        _require_digest(entry["content"], entry["content_digest"], "E_SDK_AGENT_MEMORY_DIGEST_MISMATCH")


def _validate_effect(payload: dict[str, Any]) -> None:
    if "arguments" in payload:
        _require_digest(payload["arguments"], payload["arguments_digest"], "E_SDK_AGENT_ARGUMENTS_DIGEST_MISMATCH")


def _validate_frame(payload: dict[str, Any]) -> None:
    direction_by_message = {
        "bootstrap": "parent_to_child",
        "capability_result": "parent_to_child",
        "cancel": "parent_to_child",
        "ready": "child_to_parent",
        "capability_call": "child_to_parent",
        "progress": "child_to_parent",
        "iteration_result": "child_to_parent",
    }
    message_type = payload["message_type"]
    if payload["direction"] != direction_by_message[message_type]:
        raise ValueError("E_SDK_AGENT_FRAME_DIRECTION_INVALID")
    is_capability = message_type in {"capability_call", "capability_result"}
    if is_capability != bool(payload["call_id"] and payload["operation"]):
        raise ValueError("E_SDK_AGENT_FRAME_CALL_ID_INVALID")
    frame_payload = payload["payload"]
    expected_type = {
        "bootstrap": "agent_iteration_request",
        "progress": "agent_progress",
        "iteration_result": "agent_iteration_result",
        "cancel": "agent_cancellation",
    }.get(message_type)
    if expected_type is not None:
        if frame_payload.get("object_type") != expected_type:
            raise ValueError("E_SDK_AGENT_FRAME_PAYLOAD_TYPE_INVALID")
        validate_governed_agent_payload(frame_payload)
    elif message_type == "ready":
        expected_keys = {"supported_protocol_versions", "supported_contract_versions"}
        if set(frame_payload) != expected_keys:
            raise ValueError("E_SDK_AGENT_READY_PAYLOAD_INVALID")
    else:
        operation_types = {
            ("capability_call", "model.call.v1"): "agent_model_call_request",
            ("capability_result", "model.call.v1"): "agent_model_call_result",
            ("capability_call", "memory.query.v1"): "agent_memory_query_request",
            ("capability_result", "memory.query.v1"): "agent_memory_query_result",
        }
        if frame_payload.get("object_type") != operation_types[(message_type, payload["operation"])]:
            raise ValueError("E_SDK_AGENT_FRAME_OPERATION_PAYLOAD_INVALID")
        if frame_payload.get("call_id") != payload["call_id"]:
            raise ValueError("E_SDK_AGENT_FRAME_CALL_ID_MISMATCH")
        validate_governed_agent_payload(frame_payload)


def _validate_budget(budget: dict[str, Any], expected_scope: str) -> None:
    if budget["scope"] != expected_scope:
        raise ValueError(f"E_SDK_AGENT_BUDGET_SCOPE_INVALID: {expected_scope}")
    _require_unique(budget["per_role_model_calls"], "role", "E_SDK_AGENT_BUDGET_ROLE_DUPLICATE")
    _require_unique(budget["per_role_inference_concurrency"], "role", "E_SDK_AGENT_BUDGET_ROLE_DUPLICATE")
    _require_unique(budget["per_capability_effects"], "capability", "E_SDK_AGENT_BUDGET_CAPABILITY_DUPLICATE")
    if any(int(item["count"]) > int(budget["model_calls"]) for item in budget["per_role_model_calls"]):
        raise ValueError("E_SDK_AGENT_ROLE_MODEL_BUDGET_EXCEEDS_TOTAL")
    if any(
        int(item["count"]) > int(budget["total_inference_concurrency"])
        for item in budget["per_role_inference_concurrency"]
    ):
        raise ValueError("E_SDK_AGENT_ROLE_CONCURRENCY_EXCEEDS_TOTAL")
    digest_payload = dict(budget)
    actual_digest = digest_payload.pop("snapshot_digest")
    _require_digest(digest_payload, actual_digest, "E_SDK_AGENT_BUDGET_DIGEST_MISMATCH")


def _validate_materialized_input(item: dict[str, Any]) -> None:
    content = item["content"]
    encoding = item["encoding"]
    if encoding == "json":
        encoded = canonical_json(content).encode("utf-8")
    elif encoding == "utf8":
        encoded = str(content).encode("utf-8")
    else:
        try:
            base64.b64decode(str(content), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("E_SDK_AGENT_BASE64_INVALID") from exc
        encoded = str(content).encode("ascii")
    if len(encoded) != int(item["encoded_bytes"]):
        raise ValueError("E_SDK_AGENT_MATERIALIZED_BYTE_COUNT_MISMATCH")
    if _prefixed_digest_bytes(encoded) != item["digest"]:
        raise ValueError("E_SDK_AGENT_MATERIALIZED_DIGEST_MISMATCH")


def _validate_usage_posture(payload: dict[str, Any]) -> None:
    posture = payload["usage_posture"]
    if posture == "estimated" and not str(payload["estimate_source"] or "").strip():
        raise ValueError("E_SDK_AGENT_USAGE_ESTIMATE_SOURCE_REQUIRED")
    if posture == "unknown" and (payload["input_tokens"] is not None or payload["output_tokens"] is not None):
        raise ValueError("E_SDK_AGENT_UNKNOWN_USAGE_COUNT_FORBIDDEN")


def _validate_identity(identity: dict[str, Any]) -> None:
    for field in ("run_id", "attempt_id", "step_id", "trace_id", "invocation_id"):
        if not str(identity[field]).strip():
            raise ValueError(f"E_SDK_AGENT_IDENTITY_INVALID: {field}")


def _require_same_identity(expected: Mapping[str, Any], actual: Mapping[str, Any], location: str) -> None:
    if dict(expected) != dict(actual):
        raise ValueError(f"E_SDK_AGENT_IDENTITY_MISMATCH: {location}")


def _require_digest(value: Any, expected: str, code: str) -> None:
    actual = _prefixed_digest_bytes(canonical_json(value).encode("utf-8"))
    if actual != expected:
        raise ValueError(code)


def _require_unique(items: Iterable[Mapping[str, Any]], field: str, code: str) -> None:
    values = [item[field] for item in items]
    if len(set(values)) != len(values):
        raise ValueError(code)


def _counter_map(items: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return {str(item[field]): int(item["count"]) for item in items}


def _budget_scalar_fields() -> tuple[str, ...]:
    return (
        "iterations", "wall_time_ms", "model_calls", "input_tokens", "output_tokens",
        "effect_proposals", "output_bytes", "artifact_bytes", "repair_attempts",
        "consecutive_failures", "repeated_states", "no_progress_iterations",
        "total_inference_concurrency",
    )


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("E_SDK_AGENT_DATETIME_TIMEZONE_REQUIRED")
    return parsed


def _json_depth(value: Any, depth: int = 0) -> int:
    if isinstance(value, dict):
        return max((_json_depth(item, depth + 1) for item in value.values()), default=depth)
    if isinstance(value, list):
        return max((_json_depth(item, depth + 1) for item in value), default=depth)
    return depth


def _prefixed_digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
