from __future__ import annotations

from copy import deepcopy
from typing import Any

from orket.application.services.kernel_action_input_service import capture_kernel_request
from orket.application.services.kernel_runtime_owner import capture_kernel_observation, current_kernel_runtime
from orket.core.contracts.kernel_observation import KernelObservation

from .canonical import digest_of
from .nervous_system_admission import admission_from_proposal
from .nervous_system_approvals import create_approval_request
from .nervous_system_commit import commit_proposal_v1
from .nervous_system_contract import (
    ADMISSION_DECISIONS_V1,
    NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
    ordered_reason_codes_v1,
)
from .nervous_system_policy import (
    NervousSystemPolicyInputs,
    capture_nervous_system_policy_inputs,
    require_nervous_system_enabled,
)
from .nervous_system_runtime_state import (
    CONTRACT_VERSION,
    append_event,
    get_current_canonical_state_digest,
    get_str,
    normalized_optional_str,
)
from .nervous_system_tokens import invalidate_tokens_for_session
from .outbound_policy_gate import apply_outbound_policy_gate


def projection_pack_v1(request: dict[str, Any], *, observation: KernelObservation | None = None) -> dict[str, Any]:
    require_nervous_system_enabled()
    request = capture_kernel_request(request)
    observed = capture_kernel_observation() if observation is None else observation
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    purpose = get_str(request, "purpose", required=True)
    if purpose != NERVOUS_SYSTEM_PURPOSE_ACTION_PATH:
        raise ValueError(f"purpose must be {NERVOUS_SYSTEM_PURPOSE_ACTION_PATH}")

    canonical_state_digest = get_str(request, "canonical_state_digest", required=False)
    if canonical_state_digest is None:
        canonical_state_digest = get_current_canonical_state_digest(session_id)

    policy_context = request.get("policy_context")
    if policy_context is None:
        policy_context = {}
    if not isinstance(policy_context, dict):
        raise ValueError("policy_context must be an object")

    tool_context_summary = request.get("tool_context_summary")
    if tool_context_summary is None:
        tool_context_summary = {}
    if not isinstance(tool_context_summary, dict):
        raise ValueError("tool_context_summary must be an object")
    outbound_policy_config = request.get("outbound_policy")
    if outbound_policy_config is not None and not isinstance(outbound_policy_config, dict):
        raise ValueError("outbound_policy must be an object")
    policy_context, policy_gate_report = apply_outbound_policy_gate(policy_context, outbound_policy_config)
    tool_context_summary, tool_context_gate_report = apply_outbound_policy_gate(
        tool_context_summary,
        outbound_policy_config,
    )

    contract_digest = digest_of(
        {
            "contract_version": CONTRACT_VERSION,
            "surface": "nervous_system_action_path_v1",
            "purpose": NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
        }
    )
    policy_digest = digest_of(policy_context)
    projection_pack = {
        "pack_id": f"pp-{digest_of({'session_id': session_id, 'trace_id': trace_id, 'request_id': request_id})[:16]}",
        "created_at": observed.timestamp,
        "purpose": NERVOUS_SYSTEM_PURPOSE_ACTION_PATH,
        "canonical": {
            "canonical_state_digest": canonical_state_digest,
            "contract_digest": contract_digest,
        },
        "policy_summary": {
            "policy_digest": policy_digest,
            "outbound_policy_gate": {
                "applied": True,
                "redaction_count": int(policy_gate_report["redaction_count"])
                + int(tool_context_gate_report["redaction_count"]),
                "redacted_paths": sorted(
                    set(policy_gate_report["redacted_paths"]) | set(tool_context_gate_report["redacted_paths"])
                ),
            },
        },
        "tool_context_summary": tool_context_summary,
    }
    projection_pack_digest = digest_of(projection_pack)
    event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="projection.issued",
        created_at=observed.timestamp,
        body={
            "projection_pack_digest": projection_pack_digest,
            "policy_digest": policy_digest,
            "contract_digest": contract_digest,
        },
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "projection_pack": projection_pack,
        "projection_pack_digest": projection_pack_digest,
        "policy_digest": policy_digest,
        "contract_digest": contract_digest,
        "canonical_state_digest": canonical_state_digest,
        "event_digest": event["event_digest"],
    }


def _admit_proposal_internal(
    *,
    session_id: str,
    trace_id: str,
    request_id: str | None,
    proposal: dict[str, Any],
    policy_inputs: NervousSystemPolicyInputs,
    observation: KernelObservation,
) -> dict[str, Any]:
    owner = current_kernel_runtime()
    proposal = capture_kernel_request(proposal)
    proposal_digest = digest_of(proposal)
    decision, reason_codes, leak_hits = admission_from_proposal(proposal, policy_inputs)
    if decision not in ADMISSION_DECISIONS_V1:
        raise ValueError("invalid admission decision")

    admission_reason_codes = ordered_reason_codes_v1(reason_codes)
    admission = {
        "decision": decision,
        "reason_codes": admission_reason_codes,
    }
    decision_digest = digest_of(admission)

    with owner.lock:
        owner.admissions_by_proposal[(session_id, proposal_digest)] = {
            "session_id": session_id,
            "trace_id": trace_id,
            "request_id": request_id,
            "proposal_digest": proposal_digest,
            "admission_decision": admission,
            "decision_digest": decision_digest,
        }

    append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="proposal.received",
        created_at=observation.timestamp,
        body={"proposal_digest": proposal_digest},
    )
    admission_event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="admission.decided",
        created_at=observation.timestamp,
        body={
            "proposal_digest": proposal_digest,
            "decision_digest": decision_digest,
            "decision": decision,
            "reason_codes": admission_reason_codes,
        },
    )

    if leak_hits:
        append_event(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            event_type="incident.detected",
            created_at=observation.timestamp,
            body={
                "stage": "admission",
                "proposal_digest": proposal_digest,
                "reason_codes": ["LEAK_DETECTED"],
                "detector_hits": list(leak_hits),
            },
        )

    response = {
        "contract_version": CONTRACT_VERSION,
        "proposal_digest": proposal_digest,
        "admission_decision": admission,
        "decision_digest": decision_digest,
        "event_digest": admission_event["event_digest"],
    }

    if decision == "NEEDS_APPROVAL":
        approval = create_approval_request(
            session_id=session_id,
            trace_id=trace_id,
            request_id=request_id,
            proposal_digest=proposal_digest,
            decision_digest=decision_digest,
            reason_codes=admission_reason_codes,
            created_at=observation.timestamp,
        )
        response["approval_id"] = approval["approval_id"]

    return deepcopy(response)


def admit_proposal_v1(
    request: dict[str, Any],
    *,
    policy_inputs: NervousSystemPolicyInputs | None = None,
    observation: KernelObservation | None = None,
) -> dict[str, Any]:
    selected = capture_nervous_system_policy_inputs() if policy_inputs is None else policy_inputs
    require_nervous_system_enabled(selected)
    request = capture_kernel_request(request)
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")

    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    proposal = request.get("proposal")
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")

    return _admit_proposal_internal(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        proposal=proposal,
        policy_inputs=selected,
        observation=capture_kernel_observation() if observation is None else observation,
    )


def end_session_v1(request: dict[str, Any], *, observation: KernelObservation | None = None) -> dict[str, Any]:
    require_nervous_system_enabled()
    request = capture_kernel_request(request)
    observed_at = (capture_kernel_observation() if observation is None else observation).observed_at
    if request.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("contract_version must be kernel_api/v1")
    session_id = get_str(request, "session_id", required=True)
    trace_id = get_str(request, "trace_id", required=True)
    request_id = get_str(request, "request_id", required=False)
    reason = normalized_optional_str(request.get("reason"))

    invalidated = invalidate_tokens_for_session(session_id=session_id, reason="session_ended", observed_at=observed_at)
    event = append_event(
        session_id=session_id,
        trace_id=trace_id,
        request_id=request_id,
        event_type="session.ended",
        created_at=observed_at.isoformat(),
        body={"reason": reason or None, "invalidated_token_count": invalidated},
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "session_id": session_id,
        "event_digest": event["event_digest"],
        "canonical_state_digest": get_current_canonical_state_digest(session_id),
        "status": "ENDED",
    }


__all__ = [
    "_admit_proposal_internal",
    "admit_proposal_v1",
    "commit_proposal_v1",
    "end_session_v1",
    "projection_pack_v1",
]
