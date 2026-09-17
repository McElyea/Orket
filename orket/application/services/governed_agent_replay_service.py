from __future__ import annotations

from dataclasses import fields
from typing import Any

from orket.application.services.governed_agent_iteration_policy import agent_payload_digest
from orket.application.services.governed_agent_terminal_history import (
    GovernedAgentTerminalHistoryConflict,
    agent_terminal_history_records,
)
from orket.core.contracts.governed_agent_replay import GovernedAgentReplayEvidence
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)
from orket_extension_sdk import validate_agent_iteration_result_against_request


class ReplayIntegrityError(ValueError):
    """Stable diagnostics without retained payload contents."""


def replay_governed_agent_evidence(run_id: str, evidence: GovernedAgentReplayEvidence) -> dict[str, Any] | None:
    if evidence.run is None and not evidence.diagnostics:
        return None
    diagnostics = list(evidence.diagnostics)
    expected = {step["step_id"]: step for step in evidence.steps if step.get("step_kind") == "governed_agent_iteration"}
    diagnostics.extend(_inventory_diagnostics(run_id, evidence, expected))
    decisions = [_compare_iteration(item, expected, evidence.run) for item in evidence.iterations]
    compared = sum(item["compared"] for item in decisions)
    if not diagnostics and decisions and all(item["matched"] for item in decisions):
        status = "matched"
    elif any(item.get("evidence_status") == "invalid" for item in decisions):
        status = "mismatch"
    else:
        status = "insufficient_evidence" if expected or decisions or diagnostics else "no_decisions"
    return {
        "object_type": "governed_agent_replay",
        "schema_version": "governed_agent_replay.v2",
        "run_id": run_id,
        "status": status,
        "scope": "recorded_continuation_decisions",
        "completeness_basis": "control_plane_iteration_steps_in_same_read_snapshot",
        "expected_count": len(expected) if evidence.run is not None and not evidence.diagnostics else None,
        "snapshot_count": len(decisions),
        "compared_count": compared,
        "matched_count": sum(item["matched"] for item in decisions),
        "diagnostics": diagnostics,
        "decisions": decisions,
        "external_effects_verified": False,
        "full_execution_verified": False,
    }


def _inventory_diagnostics(run_id: str, evidence: GovernedAgentReplayEvidence, expected: dict) -> list[str]:
    diagnostics = []
    try:
        agent_terminal_history_records(evidence)
    except GovernedAgentTerminalHistoryConflict:
        diagnostics.append("terminal_authority_conflict")
    run = evidence.run or {}
    attempts = {item.get("attempt_id") for item in evidence.attempts}
    if run.get("run_id") != run_id:
        diagnostics.append("run_identity_missing_or_mismatched")
    if run.get("current_attempt_id") and run["current_attempt_id"] not in attempts:
        diagnostics.append("current_attempt_missing")
    seen: set[str] = set()
    ordinals = []
    for item in evidence.iterations:
        binding = item.get("binding") or {}
        step_id = binding.get("step_id")
        if not isinstance(step_id, str):
            diagnostics.append("iteration_step_identity_invalid")
            continue
        if step_id in seen:
            diagnostics.append(f"duplicate_step_snapshot:{step_id}")
        seen.add(step_id)
        ordinal = binding.get("iteration_ordinal")
        if type(ordinal) is int:
            ordinals.append(ordinal)
        else:
            diagnostics.append("iteration_ordinal_invalid")
    diagnostics.extend(f"snapshot_missing:{step_id}" for step_id in sorted(set(expected) - seen))
    diagnostics.extend(f"step_record_missing:{step_id}" for step_id in sorted(seen - set(expected), key=str))
    if sorted(ordinals) != list(range(1, len(ordinals) + 1)):
        diagnostics.append("iteration_sequence_incomplete")
    if run.get("final_truth_record_id"):
        truth = evidence.final_truth
        if truth is None or truth.get("run_id") != run_id:
            diagnostics.append("final_truth_missing_or_mismatched")
        elif str(truth.get("authoritative_result_ref")).partition(":")[0] in {"agent-result", "agent-decision"} and (
            truth.get("authoritative_result_ref") not in {
            f"agent-{kind}:{item['invocation_id']}" for item in evidence.iterations for kind in ("result", "decision")
            }
        ):
            diagnostics.append("terminal_snapshot_missing")
    return diagnostics


def _compare_iteration(item: dict, expected: dict, run: Any) -> dict[str, Any]:
    result = {"invocation_id": item.get("invocation_id"), "matched": False, "compared": False}
    if item.get("evidence_error"):
        return {**result, "evidence_status": "invalid", "reason": item["evidence_error"]}
    missing = [key for key in ("binding", "request", "result", "result_digest", "decision_inputs",
                              "decision", "decision_digest", "decision_inputs_digest") if item.get(key) is None]
    if missing:
        return {**result, "evidence_status": "missing", "reason": "evidence_missing", "missing_fields": missing}
    try:
        _validate_evidence(item, expected, run or {})
        inputs = _validated_inputs(item["decision_inputs"])
    except ReplayIntegrityError as exc:
        return {**result, "evidence_status": "invalid", "reason": str(exc)}
    except (KeyError, TypeError, ValueError):
        # SDK validation errors can quote retained values; keep public diagnostics bounded.
        return {**result, "evidence_status": "invalid", "reason": "evidence_integrity_invalid"}
    replayed = decide_governed_agent_continuation(inputs).to_payload()
    digest = agent_payload_digest(replayed)
    matched = replayed == item["decision"] and digest == item["decision_digest"]
    return {
        **result, "matched": matched, "compared": True,
        "evidence_status": "verified" if matched else "invalid",
        "reason": "decision_matched" if matched else "decision_mismatch",
        "recorded_decision_digest": item["decision_digest"], "replayed_decision_digest": digest,
        "rule": replayed["rule"], "disposition": replayed["disposition"],
    }


def _validate_evidence(item: dict, expected: dict, run: dict) -> None:
    binding, request = item["binding"], item["request"]
    if not isinstance(binding.get("step_id"), str):
        raise ReplayIntegrityError("step_binding_invalid")
    step = expected.get(binding.get("step_id"))
    if step is None or binding.get("attempt_id") != step.get("attempt_id"):
        raise ReplayIntegrityError("step_binding_mismatch")
    if binding.get("run_id") != run.get("run_id") or binding.get("policy_digest") != run.get("policy_digest"):
        raise ReplayIntegrityError("run_binding_mismatch")
    if item.get("invocation_id") != binding.get("invocation_id"):
        raise ReplayIntegrityError("invocation_binding_mismatch")
    identity = request["identity"]
    if not isinstance(identity, dict):
        raise ReplayIntegrityError("request_identity_invalid")
    if any(identity.get(key) != binding.get(key) for key in (
        "run_id", "attempt_id", "step_id", "invocation_id", "iteration_ordinal", "fencing_generation",
    )):
        raise ReplayIntegrityError("request_binding_mismatch")
    if binding.get("request_digest") != step.get("input_ref"):
        raise ReplayIntegrityError("step_request_digest_mismatch")
    for payload, digest in ((request, binding["request_digest"]), (item["result"], item["result_digest"]),
                            (item["decision"], item["decision_digest"]),
                            (item["decision_inputs"], item["decision_inputs_digest"])):
        if agent_payload_digest(payload) != digest:
            raise ReplayIntegrityError("evidence_digest_mismatch")
    validate_agent_iteration_result_against_request(request=request, result=item["result"])
    if step.get("output_ref") and step["output_ref"] != f"agent-result:{item['invocation_id']}":
        raise ReplayIntegrityError("step_result_reference_mismatch")
    if step.get("closure_classification") == "step_completed" and (
        f"agent-decision:{item['invocation_id']}" not in step.get("receipt_refs", [])
    ):
        raise ReplayIntegrityError("step_decision_reference_missing")


def _validated_inputs(payload: dict) -> GovernedAgentContinuationInputs:
    for field in fields(GovernedAgentContinuationInputs):
        value = payload.get(field.name)
        if field.type in (bool, "bool") and field.name in payload and type(value) is not bool:
            raise ReplayIntegrityError(f"decision_input_type_invalid:{field.name}")
    for name in ("repeated_state_count", "no_progress_count"):
        if name in payload and (type(payload[name]) is not int or payload[name] < 0):
            raise ReplayIntegrityError(f"decision_input_type_invalid:{name}")
    if payload.get("extension_recommendation") not in ("continue", "pause", "stop", "complete"):
        raise ReplayIntegrityError("decision_recommendation_invalid")
    refs = payload.get("operator_action_refs", ())
    if not isinstance(refs, (list, tuple)) or any(not isinstance(ref, str) or not ref for ref in refs):
        raise ReplayIntegrityError("decision_operator_references_invalid")
    if payload.get("progress_projection_version", "governed_agent_progress.v1") != "governed_agent_progress.v1":
        raise ReplayIntegrityError("decision_progress_version_unsupported")
    return GovernedAgentContinuationInputs(**payload)
