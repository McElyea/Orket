"""Serialized application commit ownership for the existing in-memory Kernel API."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_runtime_owner import capture_kernel_observation, current_kernel_runtime
from orket.core.contracts.kernel_observation import KernelObservation

from .canonical import digest_of
from .nervous_system_authorization import authorization_refusal_for_admission
from .nervous_system_contract import COMMIT_STATUSES_V1, ordered_reason_codes_v1
from .nervous_system_leaks import find_leak_hits, sanitize_text
from .nervous_system_policy import require_nervous_system_enabled
from .nervous_system_runtime_state import (
    CONTRACT_VERSION,
    append_event,
    get_current_canonical_state_digest,
    get_str,
    has_admission_event,
    normalized_optional_str,
    set_current_canonical_state_digest,
)

logger = logging.getLogger(__name__)


@dataclass
class CommitObservation:
    status: str = "COMMITTED"
    sanitization_digest: str = ""
    reason_codes: list[str] = field(default_factory=list)
    validation_performed: bool = False


def commit_proposal_v1(request: dict[str, Any], *, observation: KernelObservation | None = None) -> dict[str, Any]:
    owner = current_kernel_runtime()
    require_nervous_system_enabled()
    request = capture_kernel_request(request)
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    proposal_digest = get_str(request, "proposal_digest", required=True)
    decision_digest = get_str(request, "admission_decision_digest", required=True)
    approval_id = normalized_optional_str(request.get("approval_id"))
    result_digest = normalized_optional_str(request.get("execution_result_digest"))
    key = (session_id, trace_id, proposal_digest, decision_digest, approval_id, result_digest)
    event_context = dict(session_id=session_id, trace_id=trace_id, request_id=request_id)
    with owner.lock:
        existing = owner.commit_results_by_key.get(key)
        if existing is not None:
            return deepcopy(existing)
        event_context["created_at"] = (capture_kernel_observation() if observation is None else observation).timestamp
        observed = CommitObservation(sanitization_digest=normalized_optional_str(request.get("sanitization_digest")))
        try:
            _evaluate_commit(request, observed, event_context, proposal_digest, decision_digest, approval_id)
        except Exception as error:
            # Public boundary preserves ERROR without exposing request payloads or exception messages.
            logger.error("Kernel commit validation failed: %s", type(error).__name__)
            observed.status = "ERROR"
        if observed.status not in COMMIT_STATUSES_V1:
            observed.status = "ERROR"
        _publish_observations(request, observed, event_context, proposal_digest, result_digest)
        canonical_after = get_str(request, "canonical_state_digest_after", required=False)
        if canonical_after and observed.status == "COMMITTED":
            set_current_canonical_state_digest(session_id, canonical_after)
        event = append_event(
            **event_context,
            event_type="commit.recorded",
            body={
                "proposal_digest": proposal_digest,
                "admission_decision_digest": decision_digest,
                "approval_id": approval_id or None,
                "execution_result_digest": result_digest or None,
                "sanitization_digest": observed.sanitization_digest or None,
                "status": observed.status,
            },
        )
        response = dict(
            contract_version=CONTRACT_VERSION,
            status=observed.status,
            commit_event_digest=event["event_digest"],
            canonical_state_digest=get_current_canonical_state_digest(session_id),
        )
        if observed.sanitization_digest:
            response["sanitization_digest"] = observed.sanitization_digest
        owner.commit_results_by_key[key] = deepcopy(response)
        return response


def _evaluate_commit(request, observed, event_context, proposal_digest, decision_digest, approval_id) -> None:
    owner = current_kernel_runtime()
    session_id = event_context["session_id"]
    admission = owner.admissions_by_proposal.get((session_id, proposal_digest))
    if (
        not admission
        or admission.get("decision_digest") != decision_digest
        or not has_admission_event(
            session_id=session_id,
            proposal_digest=proposal_digest,
            admission_decision_digest=decision_digest,
        )
    ):
        observed.status = "REJECTED_PRECONDITION"
        return
    observed.status = (
        authorization_refusal_for_admission(
            admission=admission,
            session_id=session_id,
            proposal_digest=proposal_digest,
            decision_digest=decision_digest,
            approval_id=approval_id,
        )
        or "COMMITTED"
    )
    if observed.status == "COMMITTED" and bool(request.get("revalidate_policy_forbidden")):
        observed.status = "REJECTED_POLICY"
    payload = request.get("execution_result_payload")
    valid = request.get("execution_result_schema_valid")
    observed.validation_performed = payload is not None or valid is not None or bool(observed.sanitization_digest)
    if observed.status == "COMMITTED" and payload is not None:
        leak_hits = find_leak_hits(payload)
        if leak_hits:
            observed.reason_codes.append("RESULT_LEAK_DETECTED")
            append_event(
                **event_context,
                event_type="incident.detected",
                body={
                    "stage": "action_result",
                    "proposal_digest": proposal_digest,
                    "reason_codes": ["RESULT_LEAK_DETECTED"],
                    "detector_hits": leak_hits,
                },
            )
            if bool(request.get("block_result_leaks")):
                observed.status = "REJECTED_POLICY"
            elif not observed.sanitization_digest and isinstance(payload, str):
                observed.sanitization_digest = digest_of({"sanitized": sanitize_text(payload)})
                observed.validation_performed = True
    if observed.status == "COMMITTED" and valid is False:
        observed.reason_codes.append("RESULT_SCHEMA_INVALID")
        observed.status = "REJECTED_POLICY"
    error_code = normalized_optional_str(request.get("execution_error_reason_code")).upper()
    if observed.status == "COMMITTED" and error_code in {"TOKEN_INVALID", "TOKEN_EXPIRED", "TOKEN_REPLAY"}:
        observed.reason_codes.append(error_code)
        observed.status = "REJECTED_POLICY"


def _publish_observations(request, observed, event_context, proposal_digest, result_digest) -> None:
    if observed.status != "ERROR" and request.get("execution_result_payload") is not None:
        append_event(
            **event_context,
            event_type="action.executed",
            body={
                "proposal_digest": proposal_digest,
                "execution_result_digest": result_digest or None,
                "status": "OBSERVED",
            },
        )
    if observed.validation_performed and observed.status != "ERROR":
        append_event(
            **event_context,
            event_type="action.result_validated",
            body={
                "proposal_digest": proposal_digest,
                "execution_result_digest": result_digest or None,
                "status": "PASS" if observed.status == "COMMITTED" else "FAIL",
                "reason_codes": ordered_reason_codes_v1(observed.reason_codes),
                "sanitization_digest": observed.sanitization_digest or None,
            },
        )
