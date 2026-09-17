"""Resolve terminal claims against retained decisions and observed effects."""

from __future__ import annotations

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_effect_authority import validate_effect_authority
from orket.application.services.outward_run_execution_plan import acceptance_tool_steps, previous_tool_results
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_effects import OutwardEffectRecord
from orket.core.domain.outward_model_admission import OutwardModelAdmission
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

TerminalCause = OutwardApprovalProposal | OutwardEffectRecord | OutwardModelAdmission | LedgerEvent


async def terminal_evidence_refs(
    transaction: OutwardStoreTransaction, run: OutwardRunRecord, *, outcome: str, cause: TerminalCause,
) -> list[str]:
    if outcome == "success":
        return await _successful_sequence_refs(transaction, run)
    if outcome in {"denied", "expired"} and isinstance(cause, OutwardApprovalProposal):
        if (cause.run_id != run.run_id or cause.status != outcome
                or await transaction.get_proposal(cause.proposal_id) != cause):
            raise RuntimeError("E_OUTWARD_TERMINAL_DECISION_CONFLICT")
        event_id = f"{cause.proposal_id}:0002:proposal_{outcome}"
        event = await transaction.get_event(event_id)
        if event is None or event.payload != cause.to_decision_payload():
            raise RuntimeError("E_OUTWARD_TERMINAL_DECISION_EVENT_MISSING")
        return [event_id]
    if outcome in {"policy_rejected", "handoff_rejected"} and isinstance(cause, LedgerEvent):
        expected = "proposal_policy_rejected" if outcome == "policy_rejected" else "trust_handoff_rejected"
        retained = await transaction.get_event(cause.event_id)
        if retained is None or retained.run_id != run.run_id or retained.event_type != expected or retained.payload != cause.payload:
            raise RuntimeError("E_OUTWARD_TERMINAL_POLICY_EVIDENCE_MISSING")
        return [retained.event_id]
    if outcome == "failed" and isinstance(cause, OutwardEffectRecord):
        proposal = await transaction.get_proposal(cause.proposal_id)
        if proposal is None or proposal.run_id != run.run_id or proposal.authorization is None:
            raise RuntimeError("E_OUTWARD_TERMINAL_EFFECT_BINDING_MISSING")
        if await transaction.effects.get(cause.effect_id) != cause or cause.state not in {"observed", "published"}:
            raise RuntimeError("E_OUTWARD_TERMINAL_EFFECT_NOT_OBSERVED")
        await validate_effect_authority(transaction, proposal.authorization, cause)
        return [f"{cause.effect_id}:receipt:sha256:{cause.receipt_digest}"]
    if outcome == "failed" and isinstance(cause, OutwardModelAdmission):
        attempts = await transaction.models.list_attempts(cause.run_id, cause.execution_generation, cause.turn, cause.step_index)
        if cause.run_id != run.run_id or not attempts or attempts[-1] != cause or cause.state not in {"observed", "published"}:
            raise RuntimeError("E_OUTWARD_TERMINAL_MODEL_EVIDENCE_MISSING")
        return [f"{cause.attempt_id}:result:sha256:{cause.result_digest}"]
    raise RuntimeError("E_OUTWARD_TERMINAL_BASIS_UNSUPPORTED")


async def _successful_sequence_refs(transaction: OutwardStoreTransaction, run: OutwardRunRecord) -> list[str]:
    steps, results = acceptance_tool_steps(run), previous_tool_results(run)
    if not steps or len(results) != len(steps):
        raise RuntimeError("E_OUTWARD_TERMINAL_SEQUENCE_INCOMPLETE")
    refs = []
    for index, (step, result) in enumerate(zip(steps, results, strict=True)):
        proposal = await transaction.get_proposal(str(result.get("proposal_id") or ""))
        if proposal is None or proposal.status != "approved" or proposal.authorization is None:
            raise RuntimeError("E_OUTWARD_TERMINAL_APPROVAL_MISSING")
        binding = proposal.authorization
        if ((binding.run_id, binding.execution_generation, binding.namespace, binding.step_index, binding.tool)
                != (run.run_id, run.execution_generation, run.namespace, index, step["tool"])):
            raise RuntimeError("E_OUTWARD_TERMINAL_SEQUENCE_BINDING_CONFLICT")
        effect = await transaction.effects.get(binding.effect_id)
        if effect is None or effect.state not in {"observed", "published"}:
            raise RuntimeError("E_OUTWARD_TERMINAL_EFFECT_NOT_OBSERVED")
        await validate_effect_authority(transaction, binding, effect)
        receipt = effect.receipt
        if receipt["event"].get("outcome") != "success" or receipt["result"] != result.get("result"):
            raise RuntimeError("E_OUTWARD_TERMINAL_EFFECT_NOT_SUCCESSFUL")
        refs.append(f"{effect.effect_id}:receipt:sha256:{effect.receipt_digest}")
    return refs
