from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_authority import ensure_governed_agent_authority
from orket.application.services.governed_agent_effect_records import (
    approval_id as effect_approval_id,
)
from orket.application.services.governed_agent_effect_records import (
    approval_payload,
    approval_view,
    content_matches,
    effect_receipt,
    post_effect_checkpoint,
    pre_effect_checkpoint,
    proposal_arguments,
)
from orket.application.services.governed_agent_effect_terminal_service import (
    close_denied_agent_effect,
    record_uncertain_agent_effect,
    reject_denied_agent_checkpoint,
)
from orket.application.services.tool_approval_control_plane_operator_service import (
    ToolApprovalControlPlaneOperatorService,
)
from orket.application.services.tool_approval_control_plane_reservation_service import (
    ToolApprovalControlPlaneReservationService,
)
from orket.core.contracts import OperatorActionRecord, RunRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentAuthorityGuard,
    GovernedAgentFileEffectExecutor,
)
from orket.core.contracts.pending_gate_repository import PendingGateRepository
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    CheckpointReobservationClass,
    ResidualUncertaintyClassification,
)
from orket_extension_sdk import (
    AgentEffectProposal,
    AgentEffectReceipt,
    AgentIterationRequest,
    canonical_digest_sha256,
)


@dataclass(frozen=True, slots=True)
class GovernedAgentEffectPreparation:
    receipt: AgentEffectReceipt
    approval_id: str | None
    checkpoint_id: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentEffectResolution:
    receipt: AgentEffectReceipt
    operator_action: OperatorActionRecord
    effect_journal_ref: str | None
    accepted_checkpoint_ref: str | None


class GovernedAgentEffectService:
    """Composes agent proposals with the existing approval, tool, and effect authorities."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
        pending_gates: PendingGateRepository,
        file_executor: GovernedAgentFileEffectExecutor,
        transactions: ControlPlaneTransactionFactory,
    ) -> None:
        self._execution = execution_repository
        self._publication = publication
        self._pending = pending_gates
        self._files = file_executor
        self._transactions = transactions
        self._operator = ToolApprovalControlPlaneOperatorService(
            publication=publication,
            execution_repository=execution_repository,
        )
        self._reservations = ToolApprovalControlPlaneReservationService(publication=publication)

    async def prepare(
        self,
        *,
        request: AgentIterationRequest,
        proposal: AgentEffectProposal,
        created_at: str,
        authority_guard: GovernedAgentAuthorityGuard | None = None,
    ) -> GovernedAgentEffectPreparation:
        await ensure_governed_agent_authority(authority_guard)
        run = await self._require_authority(request, proposal)
        issue_id, arguments = proposal_arguments(proposal)
        if proposal.capability == "read_file":
            receipt = await self._observe_effect(proposal, issue_id, arguments, created_at, authority_guard)
            return GovernedAgentEffectPreparation(receipt, None, None)
        if proposal.capability != "write_file":
            raise ValueError("E_AGENT_EFFECT_CAPABILITY_UNSUPPORTED")
        checkpoint = pre_effect_checkpoint(request, proposal, created_at)
        if await self._publication.repository.get_checkpoint(checkpoint_id=checkpoint.checkpoint_id) is None:
            await ensure_governed_agent_authority(authority_guard)
            await self._publication.publish_checkpoint(checkpoint=checkpoint)
        approval_id_for_proposal = effect_approval_id(proposal)
        await ensure_governed_agent_authority(authority_guard)
        await self._pending.create_request(
            request_id=approval_id_for_proposal,
            session_id=proposal.identity.run_id,
            issue_id=issue_id,
            seat_name="governed-agent",
            gate_mode="approval_required",
            request_type="tool_approval",
            reason="approval_required_tool:write_file",
            created_at=created_at,
            payload={
                "tool": "write_file",
                "args": arguments,
                "role": "governed-agent",
                "turn_index": proposal.identity.iteration_ordinal,
                "control_plane_target_ref": run.run_id,
                "attempt_id": proposal.identity.attempt_id,
                "step_id": proposal.identity.step_id,
                "proposal": proposal.to_wire(),
                "checkpoint_id": checkpoint.checkpoint_id,
            },
        )
        reservation_id = self._reservations.reservation_id(approval_id_for_proposal)
        if await self._publication.repository.get_latest_reservation_record(reservation_id=reservation_id) is None:
            await ensure_governed_agent_authority(authority_guard)
            await self._reservations.publish_pending_tool_approval_hold(
                approval_id=approval_id_for_proposal,
                session_id=proposal.identity.run_id,
                issue_id=issue_id,
                seat_name="governed-agent",
                tool_name="write_file",
                turn_index=proposal.identity.iteration_ordinal,
                created_at=created_at,
                control_plane_target_ref=run.run_id,
            )
        await ensure_governed_agent_authority(authority_guard)
        return GovernedAgentEffectPreparation(
            effect_receipt(
                proposal,
                "proposed",
                f"approval-request:{approval_id_for_proposal}",
                (checkpoint.checkpoint_id,),
            ),
            approval_id_for_proposal,
            checkpoint.checkpoint_id,
        )

    async def resolve_write(
        self,
        *,
        approval_id: str,
        decision: str,
        actor_ref: str,
        timestamp: str,
    ) -> GovernedAgentEffectResolution:
        previous = await self._approval(approval_id)
        if previous is None:
            raise ValueError("E_AGENT_EFFECT_APPROVAL_NOT_FOUND")
        normalized_decision = str(decision).strip().lower()
        if normalized_decision not in {"approved", "denied"}:
            raise ValueError("E_AGENT_EFFECT_APPROVAL_DECISION_INVALID")
        previous_status = str(previous.get("status") or "").lower()
        if previous_status == normalized_decision:
            return await self._existing_resolution(previous, normalized_decision)
        if previous_status != "pending":
            raise ValueError("E_AGENT_EFFECT_APPROVAL_ALREADY_RESOLVED")
        if normalized_decision == "denied":
            async with self._transactions() as transaction:
                scoped = GovernedAgentEffectService(
                    execution_repository=transaction.execution,
                    publication=ControlPlanePublicationService(repository=transaction.records),
                    pending_gates=transaction.pending_gates, file_executor=self._files,
                    transactions=self._transactions,
                )
                return await scoped._resolve_pending(previous, normalized_decision, actor_ref, timestamp)
        return await self._resolve_pending(previous, normalized_decision, actor_ref, timestamp)

    async def _resolve_pending(self, previous, normalized_decision, actor_ref, timestamp):
        approval_id = str(previous["request_id"])
        claimed = await self._pending.resolve_request(
            request_id=approval_id,
            status=normalized_decision,
            resolution={"decision": normalized_decision},
            resolved_at=timestamp,
            expected_status="pending",
        )
        if not claimed:
            raise ValueError("E_AGENT_EFFECT_APPROVAL_ALREADY_RESOLVED")
        resolved = await self._approval(approval_id)
        if resolved is None:
            raise ValueError("E_AGENT_EFFECT_APPROVAL_RESOLUTION_MISSING")
        operator_action = await self._operator.publish_resolution_operator_action(
            actor_ref=actor_ref,
            previous_approval=approval_view(previous),
            resolved_approval=approval_view(resolved),
        )
        await self._reservations.publish_resolved_tool_approval_hold(resolved_approval=approval_view(resolved))
        payload = approval_payload(resolved)
        proposal = AgentEffectProposal.from_wire(cast(dict[str, Any], payload["proposal"]))
        checkpoint_id = str(payload["checkpoint_id"])
        if normalized_decision == "denied":
            await reject_denied_agent_checkpoint(self._publication, checkpoint_id, proposal, timestamp)
            await close_denied_agent_effect(
                execution_repository=self._execution,
                publication=self._publication,
                proposal=proposal,
                timestamp=timestamp,
                approval_action=operator_action,
            )
            return GovernedAgentEffectResolution(
                effect_receipt(proposal, "denied", operator_action.action_id, (checkpoint_id,)),
                operator_action,
                None,
                None,
            )
        return await self._execute_approved(
            proposal=proposal,
            arguments=cast(dict[str, Any], payload["args"]),
            issue_id=str(resolved["issue_id"]),
            timestamp=timestamp,
            operator_action=operator_action,
        )

    async def _existing_resolution(self, approval: dict[str, Any], decision: str) -> GovernedAgentEffectResolution:
        payload = approval_payload(approval)
        proposal = AgentEffectProposal.from_wire(cast(dict[str, Any], payload["proposal"]))
        actions = await self._publication.repository.list_operator_actions(
            target_ref=f"approval-request:{approval['request_id']}"
        )
        if not actions:
            raise ValueError("E_AGENT_EFFECT_OPERATOR_ACTION_MISSING")
        action = actions[-1]
        if decision == "denied":
            receipt = effect_receipt(proposal, "denied", action.action_id, (str(payload["checkpoint_id"]),))
            return GovernedAgentEffectResolution(receipt, action, None, None)
        entry = await self._existing_effect_entry(proposal)
        if entry is None:
            return await self._execute_approved(
                proposal=proposal, arguments=cast(dict[str, Any], payload["args"]),
                issue_id=str(approval["issue_id"]), timestamp=str(approval["resolved_at"]),
                operator_action=action, reconciliation_only=True,
            )
        if entry.uncertainty_classification is not ResidualUncertaintyClassification.NONE:
            raise ValueError("E_AGENT_EFFECT_RECONCILIATION_REQUIRED")
        receipt = effect_receipt(proposal, "observed", action.action_id, (entry.observed_result_ref, entry.journal_entry_id))
        return GovernedAgentEffectResolution(receipt, action, entry.journal_entry_id, None)

    async def _execute_approved(
        self,
        *,
        proposal: AgentEffectProposal,
        arguments: dict[str, Any],
        issue_id: str,
        timestamp: str,
        operator_action: OperatorActionRecord,
        reconciliation_only: bool = False,
    ) -> GovernedAgentEffectResolution:
        existing = await self._existing_effect_entry(proposal)
        if existing is not None:
            receipt = effect_receipt(
                proposal,
                "observed",
                existing.authorization_basis_ref,
                (existing.observed_result_ref or "",),
            )
            return GovernedAgentEffectResolution(receipt, operator_action, existing.journal_entry_id, None)
        observed_before = await self._files.observe(path=str(arguments["path"]), issue_id=issue_id)
        intended_content = arguments["content"]
        reconciled = bool(observed_before.get("ok")) and content_matches(
            observed_before.get("content"), intended_content
        )
        if reconciliation_only and not reconciled:
            raise ValueError("E_AGENT_EFFECT_RECONCILIATION_REQUIRED")
        outcome = (
            observed_before
            if reconciled
            else await self._files.write(path=str(arguments["path"]), content=intended_content, issue_id=issue_id)
        )
        if not bool(outcome.get("ok")):
            return await self._uncertain_effect(proposal, timestamp, operator_action)
        observed = await self._files.observe(path=str(arguments["path"]), issue_id=issue_id)
        if not bool(observed.get("ok")) or not content_matches(observed.get("content"), intended_content):
            return await self._uncertain_effect(proposal, timestamp, operator_action)
        observed_ref = "sha256:" + cast(str, canonical_digest_sha256(observed.get("content")))
        journal = await self._append_journal(
            proposal, timestamp, operator_action.action_id, observed_ref, ResidualUncertaintyClassification.NONE
        )
        checkpoint_ref = await self._accept_post_effect_checkpoint(proposal, journal, timestamp)
        state: Literal["reconciled", "observed"] = "reconciled" if reconciled else "observed"
        receipt = effect_receipt(proposal, state, operator_action.action_id, (observed_ref, journal.journal_entry_id))
        return GovernedAgentEffectResolution(receipt, operator_action, journal.journal_entry_id, checkpoint_ref)

    async def _observe_effect(
        self,
        proposal: AgentEffectProposal,
        issue_id: str,
        arguments: dict[str, Any],
        timestamp: str,
        authority_guard: GovernedAgentAuthorityGuard | None,
    ) -> AgentEffectReceipt:
        await ensure_governed_agent_authority(authority_guard)
        observed = await self._files.observe(path=str(arguments["path"]), issue_id=issue_id)
        await ensure_governed_agent_authority(authority_guard)
        if not bool(observed.get("ok")):
            journal = await record_uncertain_agent_effect(
                execution_repository=self._execution,
                publication=self._publication,
                proposal=proposal,
                timestamp=timestamp,
                authority_ref="host-observe-policy:v1",
            )
            return effect_receipt(proposal, "uncertain", "host-observe-policy:v1", (journal.journal_entry_id,))
        observed_ref = "sha256:" + cast(str, canonical_digest_sha256(observed.get("content")))
        journal = await self._append_journal(
            proposal, timestamp, "host-observe-policy:v1", observed_ref, ResidualUncertaintyClassification.NONE
        )
        return effect_receipt(
            proposal,
            "observed",
            "host-observe-policy:v1",
            (observed_ref, journal.journal_entry_id),
        )

    async def _uncertain_effect(
        self, proposal: AgentEffectProposal, timestamp: str, operator_action: OperatorActionRecord
    ) -> GovernedAgentEffectResolution:
        journal = await record_uncertain_agent_effect(
            execution_repository=self._execution,
            publication=self._publication,
            proposal=proposal,
            timestamp=timestamp,
            authority_ref=operator_action.action_id,
        )
        receipt = effect_receipt(proposal, "uncertain", operator_action.action_id, (journal.journal_entry_id,))
        return GovernedAgentEffectResolution(receipt, operator_action, journal.journal_entry_id, None)

    async def _append_journal(self, proposal, timestamp, authority_ref, observed_ref, uncertainty):
        return await self._publication.append_effect_journal_entry(
            journal_entry_id=f"agent-effect-journal:{proposal.proposal_id}:{uncertainty.value}",
            effect_id=f"agent-effect:{proposal.proposal_id}",
            run_id=proposal.identity.run_id,
            attempt_id=proposal.identity.attempt_id,
            step_id=proposal.identity.step_id,
            authorization_basis_ref=authority_ref,
            publication_timestamp=timestamp,
            intended_target_ref=proposal.intended_target,
            observed_result_ref=observed_ref,
            uncertainty_classification=uncertainty,
            integrity_verification_ref=proposal.arguments_digest,
        )

    async def _existing_effect_entry(self, proposal):
        entries = await self._publication.repository.list_effect_journal_entries(run_id=proposal.identity.run_id)
        return next((entry for entry in entries if entry.effect_id == f"agent-effect:{proposal.proposal_id}"), None)
    async def _accept_post_effect_checkpoint(self, proposal, journal, timestamp) -> str:
        pre_checkpoint = await self._publication.repository.get_checkpoint(
            checkpoint_id=f"agent-pre-effect-checkpoint:{proposal.proposal_id}"
        )
        if pre_checkpoint is None:
            raise ValueError("E_AGENT_EFFECT_CHECKPOINT_MISSING")
        checkpoint = post_effect_checkpoint(proposal, journal, timestamp, pre_checkpoint.policy_digest)
        acceptance = await self._publication.accept_checkpoint(
            acceptance_id=f"agent-effect-checkpoint-acceptance:{proposal.proposal_id}",
            checkpoint=checkpoint,
            supervisor_authority_ref="governed-agent-effect-service:v1",
            decision_timestamp=timestamp,
            required_reobservation_class=CheckpointReobservationClass.NONE,
            integrity_verification_ref=journal.entry_digest,
            journal_entries=(journal,),
            dependent_effect_entry_refs=(journal.journal_entry_id,),
        )
        return str(acceptance.checkpoint_id)

    async def _approval(self, approval_id: str) -> dict[str, Any] | None:
        rows = await self._pending.list_requests(limit=1000)
        return next((row for row in rows if str(row.get("request_id")) == approval_id), None)

    async def _require_authority(self, request, proposal) -> RunRecord:
        if proposal.identity != request.identity:
            raise ValueError("E_AGENT_EFFECT_IDENTITY_MISMATCH")
        if (
            proposal.capability not in request.admitted_capabilities
            or proposal.namespace not in request.namespace_scope
        ):
            raise ValueError("E_AGENT_EFFECT_AUTHORITY_UNADMITTED")
        run = await self._execution.get_run_record(run_id=proposal.identity.run_id)
        if run is None or run.current_attempt_id != proposal.identity.attempt_id:
            raise ValueError("E_AGENT_EFFECT_RUN_AUTHORITY_MISSING")
        if run.namespace_scope != proposal.namespace:
            raise ValueError("E_AGENT_EFFECT_NAMESPACE_DRIFT")
        return run
