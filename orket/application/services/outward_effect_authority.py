"""Shared validation of retained outward bindings, receipts and recovery fences."""

from __future__ import annotations

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_effect_recovery_records import validate_recovered_owner
from orket.core.domain.control_plane_effect_journal import validate_effect_journal_chain
from orket.core.domain.outward_authorization import OutwardAuthorization
from orket.core.domain.outward_effects import OutwardEffectRecord, effect_journal_entry_id


async def validate_effect_authority(
    transaction: OutwardStoreTransaction, binding: OutwardAuthorization, effect: OutwardEffectRecord,
) -> None:
    entries = validate_effect_journal_chain(await transaction.effects.list_journal(binding.run_id))
    matching = [entry for entry in entries if entry.journal_entry_id == effect.journal_entry_id]
    if effect.binding_digest != binding.digest or effect.proposal_id != binding.proposal_id or len(matching) != 1:
        raise RuntimeError("E_OUTWARD_EFFECT_AUTHORITY_MISMATCH")
    entry = matching[0]
    if (entry.effect_id != binding.effect_id or entry.attempt_id != binding.attempt_id
            or entry.journal_entry_id != effect_journal_entry_id(binding.effect_id, effect.state, effect.fencing_generation)
            or entry.intended_target_ref != binding.target_ref
            or entry.authorization_basis_ref != f"{binding.proposal_id}:sha256:{binding.digest}"):
        raise RuntimeError("E_OUTWARD_EFFECT_JOURNAL_MISMATCH")
    if effect.receipt_digest and entry.observed_result_ref != f"{binding.effect_id}:receipt:sha256:{effect.receipt_digest}":
        raise RuntimeError("E_OUTWARD_EFFECT_RECEIPT_JOURNAL_MISMATCH")
    if effect.recovery_decision_id is not None:
        validate_recovered_owner(
            binding, effect, await transaction.recovery.get(effect.recovery_decision_id),
            claim_entry_id=effect_journal_entry_id(effect.effect_id, "claimed", effect.fencing_generation),
        )
