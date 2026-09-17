from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction, OutwardStoreUnitOfWork
from orket.application.services.outward_authorization_service import (
    validate_dispatch_authorization,
    validate_run_authorization,
)
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.application.services.outward_control_plane_service import require_outward_authority
from orket.application.services.outward_effect_authority import validate_effect_authority
from orket.application.services.outward_effect_publication import publish_effect_projection
from orket.application.services.outward_effect_recovery_records import (
    recovery_records,
    validate_recovery_retry,
)
from orket.application.services.outward_run_execution_plan import acceptance_tool_steps
from orket.core.contracts.control_plane_effect_journal_models import EffectJournalEntryRecord
from orket.core.domain.control_plane_effect_journal import create_effect_journal_entry, validate_effect_journal_chain
from orket.core.domain.control_plane_enums import ResidualUncertaintyClassification
from orket.core.domain.outward_authorization import OutwardAuthorization, args_hash, canonical_json
from orket.core.domain.outward_effects import OutwardEffectRecord, OutwardEffectRecoveryRequest, effect_journal_entry_id
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardEffectService:
    def __init__(
        self, *, unit_of_work: OutwardStoreUnitOfWork, connectors: OutwardConnectorService,
        utc_now: Callable[[], str], owner_id_factory: Callable[[], str],
    ) -> None:
        self.unit_of_work, self.connectors = unit_of_work, connectors
        self.utc_now, self.owner_id_factory = utc_now, owner_id_factory

    async def execute(self, proposal_id: str) -> tuple[OutwardRunRecord, bool]:
        return await self._execute_claim(*await self._claim(proposal_id))

    async def recover(self, request: OutwardEffectRecoveryRequest) -> tuple[OutwardRunRecord, bool]:
        return await self._execute_claim(*await self._recover_claim(request))

    async def inspect(self, proposal_id: str) -> dict[str, Any]:
        async with self.unit_of_work.transaction() as transaction:
            proposal = await transaction.get_proposal(proposal_id)
            if proposal is None:
                raise ValueError(f"Approval proposal '{proposal_id}' not found")
            binding = proposal.authorization
            effect = await transaction.effects.get(binding.effect_id) if binding else None
            if effect is not None:
                await validate_effect_authority(transaction, binding, effect)
            return {
                "proposal_id": proposal_id, "approval_status": proposal.status,
                "effect_id": binding.effect_id if binding else None,
                "binding_digest": binding.digest if binding else None,
                "state": effect.state if effect else "unclaimed" if binding else "legacy_unbound",
                "owner_id": effect.owner_id if effect else None,
                "fencing_generation": effect.fencing_generation if effect else None,
                "journal_entry_id": effect.journal_entry_id if effect else None,
                "receipt_digest": effect.receipt_digest if effect else None,
                "claimed_at": effect.claimed_at if effect else None,
                "dispatched_at": effect.dispatched_at if effect else None,
                "published_at": effect.published_at if effect else None,
                "recovery_decision_id": effect.recovery_decision_id if effect else None,
            }

    async def _execute_claim(
        self, run: OutwardRunRecord, binding: OutwardAuthorization | None, effect: OutwardEffectRecord | None, owned: bool,
    ) -> tuple[OutwardRunRecord, bool]:
        if effect is None or effect.state == "published":
            return run, False
        if binding is None:
            raise RuntimeError("E_OUTWARD_AUTHORIZATION_REQUIRED")
        if owned:
            effect = await self._intent(binding, effect)
            # Cancellation/crash/unknown failure retains dispatch intent; it never permits another invocation.
            event, result = await self.connectors.invoke_with_result(binding.tool, binding.arguments, authorization=binding)
            effect = await self._observe(binding, effect, event, result)
        return await self._publish(binding, effect)

    async def _recover_claim(
        self, request: OutwardEffectRecoveryRequest,
    ) -> tuple[OutwardRunRecord, OutwardAuthorization, OutwardEffectRecord, bool]:
        async with self.unit_of_work.transaction() as transaction:
            proposal = await transaction.get_proposal(request.proposal_id)
            if proposal is None:
                raise ValueError(f"Approval proposal '{request.proposal_id}' not found")
            binding = proposal.authorization
            if proposal.status != "approved" or binding is None:
                raise RuntimeError("E_OUTWARD_AUTHORIZATION_REQUIRED")
            effect = await transaction.effects.get(binding.effect_id)
            run = await transaction.get_run(binding.run_id)
            if effect is None or run is None:
                raise RuntimeError("E_OUTWARD_RECOVERY_CLAIM_REQUIRED")
            await require_outward_authority(transaction, run)
            await validate_effect_authority(transaction, binding, effect)
            existing = await transaction.recovery.get(request.decision_id)
            if existing is not None:
                validate_recovery_retry(request, binding, effect, existing)
                if effect.state == "dispatching":
                    raise RuntimeError("E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN")
                return run, binding, effect, effect.state == "claimed"
            if effect.state != "claimed" or effect.dispatched_at is not None:
                raise RuntimeError("E_OUTWARD_RECOVERY_REQUIRES_PRE_INTENT_CLAIM")
            if (effect.owner_id, effect.fencing_generation) != (request.expected_owner_id, request.expected_fencing_generation):
                raise RuntimeError("E_OUTWARD_EFFECT_FENCE_CONFLICT")
            if run.status != "running":
                raise RuntimeError("E_OUTWARD_EFFECT_RUN_NOT_DISPATCHABLE")
            await validate_dispatch_authorization(binding, run, self.connectors)
            at, owner = self.utc_now(), self.owner_id_factory()
            if owner == effect.owner_id:
                raise RuntimeError("E_OUTWARD_RECOVERY_OWNER_COLLISION")
            entry = await self._journal(
                transaction, binding, state="claimed", at=at, fencing_generation=effect.fencing_generation + 1,
            )
            replacement = replace(
                effect, owner_id=owner, fencing_generation=effect.fencing_generation + 1, journal_entry_id=entry.journal_entry_id,
                recovery_decision_id=request.decision_id,
            )
            decision, action = recovery_records(request, binding, effect, replacement, at=at)
            await transaction.effects.replace_claim_owner(effect, replacement)
            await transaction.recovery.save(decision, action)
            return run, binding, replacement, True

    async def _claim(
        self, proposal_id: str,
    ) -> tuple[OutwardRunRecord, OutwardAuthorization | None, OutwardEffectRecord | None, bool]:
        async with self.unit_of_work.transaction() as transaction:
            proposal = await transaction.get_proposal(proposal_id)
            if proposal is None:
                raise RuntimeError("E_OUTWARD_PROPOSAL_NOT_FOUND")
            run = await transaction.get_run(proposal.run_id)
            if run is None:
                raise RuntimeError("E_OUTWARD_RUN_NOT_FOUND")
            await require_outward_authority(transaction, run)
            if proposal.status != "approved":
                return run, None, None, False
            binding = proposal.authorization
            if binding is None:
                raise RuntimeError("E_OUTWARD_AUTHORIZATION_REQUIRED")
            existing = await transaction.effects.get(binding.effect_id)
            if existing is not None:
                await validate_effect_authority(transaction, binding, existing)
                if existing.state in {"claimed", "dispatching"}:
                    raise RuntimeError("E_OUTWARD_EFFECT_IN_FLIGHT_OR_UNCERTAIN")
                return run, binding, existing, False
            if run.status in {"completed", "failed"} or not acceptance_tool_steps(run):
                return run, binding, None, False
            await validate_dispatch_authorization(binding, run, self.connectors)
            at = self.utc_now()
            entry = await self._journal(transaction, binding, state="claimed", at=at)
            effect = OutwardEffectRecord(
                effect_id=binding.effect_id, proposal_id=binding.proposal_id, binding_digest=binding.digest,
                owner_id=self.owner_id_factory(), fencing_generation=1, state="claimed", claimed_at=at,
                journal_entry_id=entry.journal_entry_id,
            )
            await transaction.effects.create(effect)
            return run, binding, effect, True

    async def _intent(self, binding: OutwardAuthorization, effect: OutwardEffectRecord) -> OutwardEffectRecord:
        async with self.unit_of_work.transaction() as transaction:
            await self._require_owner(transaction, binding, effect, "claimed")
            run = await transaction.get_run(binding.run_id)
            if run is None or run.status != "running":
                raise RuntimeError("E_OUTWARD_EFFECT_RUN_NOT_DISPATCHABLE")
            await validate_dispatch_authorization(binding, run, self.connectors)
            at = self.utc_now()
            entry = await self._journal(transaction, binding, state="dispatching", at=at, fencing_generation=effect.fencing_generation)
            intended = replace(effect, state="dispatching", dispatched_at=at, journal_entry_id=entry.journal_entry_id)
            await transaction.effects.transition(intended, expected_state="claimed")
            return intended

    async def _observe(
        self, binding: OutwardAuthorization, effect: OutwardEffectRecord,
        event: dict[str, Any], result: dict[str, Any],
    ) -> OutwardEffectRecord:
        async with self.unit_of_work.transaction() as transaction:
            await self._require_owner(transaction, binding, effect, "dispatching")
            at = self.utc_now()
            receipt = {"event": event, "result": result, "observed_at": at}
            digest = args_hash(receipt)
            entry = await self._journal(
                transaction, binding, state="observed", at=at, receipt_digest=digest,
                successful=event.get("outcome") == "success",
                fencing_generation=effect.fencing_generation,
            )
            observed = replace(
                effect, state="observed", receipt_json=canonical_json(receipt), receipt_digest=digest,
                journal_entry_id=entry.journal_entry_id,
            )
            await transaction.effects.transition(observed, expected_state="dispatching")
            return observed

    async def _publish(self, binding: OutwardAuthorization, effect: OutwardEffectRecord) -> tuple[OutwardRunRecord, bool]:
        async with self.unit_of_work.transaction() as transaction:
            current = await transaction.effects.get(effect.effect_id)
            if current is None:
                raise RuntimeError("E_OUTWARD_EFFECT_MISSING")
            await validate_effect_authority(transaction, binding, current)
            run = await transaction.get_run(binding.run_id)
            if run is None:
                raise RuntimeError("E_OUTWARD_RUN_NOT_FOUND")
            await require_outward_authority(transaction, run)
            if current.state == "published":
                return run, False
            if current.state != "observed":
                raise RuntimeError("E_OUTWARD_EFFECT_NOT_OBSERVED")
            # Publication checks the original turn; it cannot replace a later run projection.
            validate_run_authorization(binding, run)
            at = self.utc_now()
            projected, advance = await publish_effect_projection(transaction, binding, current, run, at=at)
            entry = await self._journal(
                transaction, binding, state="published", at=at, receipt_digest=current.receipt_digest,
                successful=current.receipt["event"].get("outcome") == "success",
                fencing_generation=current.fencing_generation,
            )
            await transaction.effects.transition(replace(
                current, state="published", published_at=at, journal_entry_id=entry.journal_entry_id,
            ), expected_state="observed")
            return projected, advance

    async def _require_owner(
        self, transaction: OutwardStoreTransaction, binding: OutwardAuthorization, effect: OutwardEffectRecord, state: str,
    ) -> None:
        run = await transaction.get_run(binding.run_id)
        if run is None:
            raise RuntimeError("E_OUTWARD_RUN_NOT_FOUND")
        await require_outward_authority(transaction, run)
        current = await transaction.effects.get(effect.effect_id)
        if current != effect or current.state != state:
            raise RuntimeError("E_OUTWARD_EFFECT_FENCE_CONFLICT")
        await validate_effect_authority(transaction, binding, current)

    async def _journal(
        self, transaction: OutwardStoreTransaction, binding: OutwardAuthorization, *, state: str, at: str,
        receipt_digest: str | None = None, successful: bool = False,
        fencing_generation: int = 1,
    ) -> EffectJournalEntryRecord:
        entries = validate_effect_journal_chain(await transaction.effects.list_journal(binding.run_id))
        entry = create_effect_journal_entry(
            journal_entry_id=effect_journal_entry_id(binding.effect_id, state, fencing_generation),
            effect_id=binding.effect_id, run_id=binding.run_id,
            attempt_id=binding.attempt_id, step_id=f"turn:{binding.turn}:step:{binding.step_index}",
            authorization_basis_ref=f"{binding.proposal_id}:sha256:{binding.digest}", publication_timestamp=at,
            intended_target_ref=binding.target_ref,
            observed_result_ref=f"{binding.effect_id}:receipt:sha256:{receipt_digest}" if receipt_digest else None,
            uncertainty_classification=(ResidualUncertaintyClassification.NONE if successful else ResidualUncertaintyClassification.UNRESOLVED),
            integrity_verification_ref=f"sha256:{binding.digest}", previous_entry=entries[-1] if entries else None,
        )
        await transaction.effects.append_journal(entry)
        return entry
