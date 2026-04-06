from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from orket.core.contracts import EffectJournalEntryRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AuthoritySourceClass,
    ClosureBasisClassification,
    CompletionClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
)

if TYPE_CHECKING:
    from orket.application.services.control_plane_publication_service import ControlPlanePublicationService


class KernelActionControlPlaneSupportError(ValueError):
    """Raised when governed action support data is incomplete."""


def authority_sources_for_commit(
    *,
    evidence: EvidenceSufficiencyClassification,
) -> list[AuthoritySourceClass]:
    if evidence is EvidenceSufficiencyClassification.SUFFICIENT:
        return [AuthoritySourceClass.RECEIPT_EVIDENCE, AuthoritySourceClass.VALIDATED_ARTIFACT]
    return [AuthoritySourceClass.RECEIPT_EVIDENCE]


def final_truth_projection_for_commit(
    *,
    status: str,
    observed_execution: bool,
    validated: bool,
    claimed_result: bool,
) -> tuple[
    ResultClass,
    CompletionClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ClosureBasisClassification,
]:
    if status == "COMMITTED":
        if validated:
            return (
                ResultClass.SUCCESS,
                CompletionClassification.SATISFIED,
                EvidenceSufficiencyClassification.SUFFICIENT,
                ResidualUncertaintyClassification.NONE,
                ClosureBasisClassification.NORMAL_EXECUTION,
            )
        return (
            ResultClass.DEGRADED,
            CompletionClassification.PARTIAL,
            EvidenceSufficiencyClassification.INSUFFICIENT,
            ResidualUncertaintyClassification.UNRESOLVED if claimed_result else ResidualUncertaintyClassification.BOUNDED,
            ClosureBasisClassification.NORMAL_EXECUTION,
        )
    if status == "ERROR":
        return (
            ResultClass.FAILED,
            CompletionClassification.UNSATISFIED,
            EvidenceSufficiencyClassification.INSUFFICIENT,
            ResidualUncertaintyClassification.UNRESOLVED,
            ClosureBasisClassification.POLICY_TERMINAL_STOP,
        )
    if observed_execution:
        return (
            ResultClass.FAILED,
            CompletionClassification.UNSATISFIED,
            EvidenceSufficiencyClassification.SUFFICIENT if validated else EvidenceSufficiencyClassification.INSUFFICIENT,
            ResidualUncertaintyClassification.NONE if validated else ResidualUncertaintyClassification.BOUNDED,
            ClosureBasisClassification.POLICY_TERMINAL_STOP,
        )
    return (
        ResultClass.BLOCKED,
        CompletionClassification.UNSATISFIED,
        EvidenceSufficiencyClassification.SUFFICIENT,
        ResidualUncertaintyClassification.NONE,
        ClosureBasisClassification.POLICY_TERMINAL_STOP,
    )


def has_observed_execution(*, request: dict[str, Any], ledger_items: Sequence[dict[str, Any]]) -> bool:
    return any(str(item.get("event_type") or "") == "action.executed" for item in ledger_items) or (
        request.get("execution_result_payload") is not None
    )


def has_validation_evidence(
    *,
    request: dict[str, Any],
    response: dict[str, Any],
    ledger_items: Sequence[dict[str, Any]],
) -> bool:
    if any(str(item.get("event_type") or "") == "action.result_validated" for item in ledger_items):
        return True
    return (
        request.get("execution_result_payload") is not None
        or request.get("execution_result_schema_valid") is not None
        or bool(response.get("sanitization_digest"))
        or bool(request.get("sanitization_digest"))
    )


def authorization_basis_ref(*, request: dict[str, Any]) -> str:
    approval_id = str(request.get("approval_id") or "").strip()
    proposal_digest = required_text(request, "proposal_digest")
    decision_digest = required_text(request, "admission_decision_digest")
    if approval_id:
        return f"kernel-authorization:{proposal_digest}:{decision_digest}:{approval_id}"
    return f"kernel-authorization:{proposal_digest}:{decision_digest}"


def run_id_for(*, session_id: str, trace_id: str) -> str:
    return f"kernel-action-run:{session_id}:{trace_id}"


def default_namespace_scope_for_session(*, session_id: str) -> str:
    normalized = str(session_id or "").strip()
    if not normalized:
        raise KernelActionControlPlaneSupportError("governed action namespace scope requires session_id")
    return f"session:{normalized}"


def resolve_namespace_scope_for_request(*, request: dict[str, Any]) -> str:
    session_id = required_text(request, "session_id")
    allowed_scope = default_namespace_scope_for_session(session_id=session_id)
    explicit_scope = optional_text(request, "namespace_scope")
    if explicit_scope is None:
        proposal = request.get("proposal")
        payload = proposal.get("payload") if isinstance(proposal, dict) else None
        if isinstance(payload, dict):
            explicit_scope = optional_text(payload, "namespace_scope")
    if explicit_scope is None:
        return allowed_scope
    if explicit_scope != allowed_scope:
        raise KernelActionControlPlaneSupportError(
            "kernel-action namespace scope escalation is not permitted: "
            f"requested={explicit_scope!r}; allowed={allowed_scope!r}"
        )
    return explicit_scope


def attempt_id_for(*, session_id: str, trace_id: str) -> str:
    return f"kernel-action-attempt:{session_id}:{trace_id}:0001"


def policy_snapshot_id_for(*, session_id: str, trace_id: str) -> str:
    return f"kernel-admission-decision:{session_id}:{trace_id}"


def configuration_snapshot_id_for(*, session_id: str, trace_id: str) -> str:
    return f"kernel-proposal:{session_id}:{trace_id}"


def starting_snapshot_ref_for(*, session_id: str, trace_id: str, proposal_digest: str) -> str:
    return f"kernel-proposal:{session_id}:{trace_id}:{proposal_digest}"


def step_id_for(*, run_id: str) -> str:
    return f"kernel-action-step:{run_id}:commit"


def target_ref_for(*, session_id: str, trace_id: str) -> str:
    return f"kernel-action-target:{session_id}:{trace_id}"


def admission_receipt_ref(
    *,
    response: dict[str, Any],
    ledger_items: Sequence[dict[str, Any]],
) -> str:
    event_digest = event_digest_for(ledger_items, "admission.decided") or str(response.get("event_digest") or "").strip()
    if event_digest:
        return f"kernel-admission-event:{event_digest}"
    decision_digest = str(response.get("decision_digest") or "").strip()
    return f"kernel-admission-decision:{decision_digest}"


def event_result_ref(
    ledger_items: Sequence[dict[str, Any]],
    event_type: str,
    response: dict[str, Any],
) -> str:
    event_digest = event_digest_for(ledger_items, event_type)
    if event_digest:
        return f"kernel-ledger-event:{event_digest}"
    fallback = str(response.get("commit_event_digest") or response.get("event_digest") or "").strip()
    return f"kernel-ledger-event:{fallback or 'missing'}"


def receipt_refs_for_commit(
    *,
    ledger_items: Sequence[dict[str, Any]],
    response: dict[str, Any],
) -> list[str]:
    refs: list[str] = []
    for event_type in ("action.executed", "action.result_validated", "commit.recorded"):
        event_ref = event_result_ref(ledger_items, event_type, response)
        if event_ref not in refs:
            refs.append(event_ref)
    return refs


def event_timestamp_for(items: Sequence[dict[str, Any]], event_type: str) -> str | None:
    for item in reversed(items):
        if str(item.get("event_type") or "") == event_type:
            value = str(item.get("created_at") or "").strip()
            if value:
                return value
    return None


def event_digest_for(items: Sequence[dict[str, Any]], event_type: str) -> str | None:
    for item in reversed(items):
        if str(item.get("event_type") or "") == event_type:
            value = str(item.get("event_digest") or "").strip()
            if value:
                return value
    return None


def proposal_digest_for(*, request: dict[str, Any], response: dict[str, Any]) -> str:
    value = str(response.get("proposal_digest") or request.get("proposal_digest") or "").strip()
    if value:
        return value
    proposal = request.get("proposal")
    if not isinstance(proposal, dict):
        raise KernelActionControlPlaneSupportError("governed action proposal digest is unavailable")
    return hash_payload(proposal)


def should_publish_step_for_commit(
    *,
    status: str,
    observed_execution: bool,
    claimed_result: bool,
    request: dict[str, Any],
) -> bool:
    if status == "COMMITTED":
        return claimed_result or request.get("execution_result_payload") is not None
    return status == "REJECTED_POLICY" and observed_execution


def build_step_record_for_commit(
    *,
    run_id: str,
    attempt_id: str,
    namespace_scope: str | None,
    request: dict[str, Any],
    response: dict[str, Any],
    ledger_items: Sequence[dict[str, Any]],
    status: str,
    observed_execution: bool,
) -> StepRecord:
    session_id = required_text(request, "session_id")
    trace_id = required_text(request, "trace_id")
    output_ref = optional_text(request, "execution_result_digest")
    if output_ref:
        output_ref = f"kernel-execution-result:{output_ref}"
    else:
        output_ref = event_result_ref(ledger_items, "commit.recorded", response)
    observed_result_classification = "kernel_action_committed"
    if status == "COMMITTED" and has_validation_evidence(request=request, response=response, ledger_items=ledger_items):
        observed_result_classification = "kernel_action_validated"
    elif status == "COMMITTED" and optional_text(request, "execution_result_digest") is not None:
        observed_result_classification = "kernel_action_claimed"
    elif observed_execution:
        observed_result_classification = "kernel_action_observed_policy_reject"
    return StepRecord(
        step_id=step_id_for(run_id=run_id),
        attempt_id=attempt_id,
        step_kind="governed_kernel_commit_execution",
        namespace_scope=namespace_scope,
        input_ref=authorization_basis_ref(request=request),
        output_ref=output_ref,
        capability_used=None,
        resources_touched=[target_ref_for(session_id=session_id, trace_id=trace_id)],
        observed_result_classification=observed_result_classification,
        receipt_refs=receipt_refs_for_commit(ledger_items=ledger_items, response=response),
        closure_classification="step_completed" if status == "COMMITTED" else "step_failed",
    )


async def publish_step_from_commit_if_missing(
    *,
    execution_repository: ControlPlaneExecutionRepository,
    run_id: str,
    attempt_id: str,
    namespace_scope: str | None,
    request: dict[str, Any],
    response: dict[str, Any],
    ledger_items: Sequence[dict[str, Any]],
    status: str,
    observed_execution: bool,
) -> StepRecord:
    step_id = step_id_for(run_id=run_id)
    existing = await execution_repository.get_step_record(step_id=step_id)
    if existing is not None:
        return existing
    return await execution_repository.save_step_record(
        record=build_step_record_for_commit(
            run_id=run_id,
            attempt_id=attempt_id,
            namespace_scope=namespace_scope,
            request=request,
            response=response,
            ledger_items=ledger_items,
            status=status,
            observed_execution=observed_execution,
        )
    )


async def publish_effect_from_commit_if_missing(
    *,
    publication: ControlPlanePublicationService,
    run_id: str,
    attempt_id: str,
    request: dict[str, Any],
    response: dict[str, Any],
    committed_at: str,
    ledger_items: Sequence[dict[str, Any]],
) -> EffectJournalEntryRecord:
    existing = await publication.repository.list_effect_journal_entries(run_id=run_id)
    if existing:
        return existing[-1]
    execution_result_digest = optional_text(request, "execution_result_digest")
    observed_result_ref = None
    uncertainty = ResidualUncertaintyClassification.UNRESOLVED
    if has_validation_evidence(request=request, response=response, ledger_items=ledger_items):
        uncertainty = ResidualUncertaintyClassification.NONE
        observed_result_ref = f"kernel-execution-result:{execution_result_digest or hash_payload(request)}"
    return await publication.append_effect_journal_entry(
        journal_entry_id=f"kernel-action-journal:{run_id}:commit",
        effect_id=f"kernel-action-effect:{run_id}:commit",
        run_id=run_id,
        attempt_id=attempt_id,
        step_id=step_id_for(run_id=run_id),
        authorization_basis_ref=authorization_basis_ref(request=request),
        publication_timestamp=committed_at,
        intended_target_ref=target_ref_for(
            session_id=required_text(request, "session_id"),
            trace_id=required_text(request, "trace_id"),
        ),
        observed_result_ref=observed_result_ref,
        uncertainty_classification=uncertainty,
        integrity_verification_ref=event_result_ref(ledger_items, "commit.recorded", response),
    )


def required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise KernelActionControlPlaneSupportError(f"missing required control-plane field: {key}")
    return value


def optional_text(payload: dict[str, Any], key: str) -> str | None:
    value = str(payload.get(key) or "").strip()
    return value or None


def hash_payload(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "KernelActionControlPlaneSupportError",
    "attempt_id_for",
    "admission_receipt_ref",
    "authority_sources_for_commit",
    "authorization_basis_ref",
    "build_step_record_for_commit",
    "configuration_snapshot_id_for",
    "default_namespace_scope_for_session",
    "event_digest_for",
    "event_result_ref",
    "event_timestamp_for",
    "final_truth_projection_for_commit",
    "has_observed_execution",
    "has_validation_evidence",
    "hash_payload",
    "optional_text",
    "policy_snapshot_id_for",
    "publish_effect_from_commit_if_missing",
    "publish_step_from_commit_if_missing",
    "proposal_digest_for",
    "receipt_refs_for_commit",
    "resolve_namespace_scope_for_request",
    "required_text",
    "run_id_for",
    "should_publish_step_for_commit",
    "starting_snapshot_ref_for",
    "step_id_for",
    "target_ref_for",
    "utc_now",
]
