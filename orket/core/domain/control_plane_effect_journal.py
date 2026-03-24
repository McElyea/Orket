from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from orket.core.domain.control_plane_enums import (
    CheckpointAcceptanceOutcome,
    ResidualUncertaintyClassification,
)

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_effect_journal_models import (
        CheckpointAcceptanceRecord,
        EffectJournalEntryRecord,
    )
    from orket.core.contracts.control_plane_models import CheckpointRecord


class ControlPlaneEffectJournalError(ValueError):
    """Raised when effect journal sequencing or integrity is invalid."""


class ControlPlaneCheckpointError(ValueError):
    """Raised when checkpoint acceptance does not match checkpoint authority."""


def _hash_canonical_payload(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def compute_effect_journal_entry_digest(entry: "EffectJournalEntryRecord") -> str:
    payload = entry.model_dump(mode="json", exclude={"entry_digest"})
    return _hash_canonical_payload(payload)


def create_effect_journal_entry(
    *,
    journal_entry_id: str,
    effect_id: str,
    run_id: str,
    attempt_id: str,
    step_id: str,
    authorization_basis_ref: str,
    publication_timestamp: str,
    intended_target_ref: str,
    observed_result_ref: str | None,
    uncertainty_classification: ResidualUncertaintyClassification,
    integrity_verification_ref: str,
    previous_entry: "EffectJournalEntryRecord | None" = None,
    contradictory_entry_refs: Sequence[str] = (),
    superseding_entry_refs: Sequence[str] = (),
) -> "EffectJournalEntryRecord":
    from orket.core.contracts.control_plane_effect_journal_models import EffectJournalEntryRecord

    base_entry = EffectJournalEntryRecord(
        journal_entry_id=journal_entry_id,
        effect_id=effect_id,
        run_id=run_id,
        attempt_id=attempt_id,
        step_id=step_id,
        authorization_basis_ref=authorization_basis_ref,
        publication_sequence=1 if previous_entry is None else previous_entry.publication_sequence + 1,
        publication_timestamp=publication_timestamp,
        intended_target_ref=intended_target_ref,
        observed_result_ref=observed_result_ref,
        uncertainty_classification=uncertainty_classification,
        integrity_verification_ref=integrity_verification_ref,
        prior_journal_entry_id=None if previous_entry is None else previous_entry.journal_entry_id,
        prior_entry_digest=None if previous_entry is None else previous_entry.entry_digest,
        contradictory_entry_refs=list(contradictory_entry_refs),
        superseding_entry_refs=list(superseding_entry_refs),
        entry_digest="pending",
    )
    return EffectJournalEntryRecord(
        **base_entry.model_dump(exclude={"entry_digest"}),
        entry_digest=compute_effect_journal_entry_digest(base_entry),
    )


def validate_effect_journal_append(
    previous_entry: "EffectJournalEntryRecord | None",
    entry: "EffectJournalEntryRecord",
) -> bool:
    expected_sequence = 1 if previous_entry is None else previous_entry.publication_sequence + 1
    if entry.publication_sequence != expected_sequence:
        raise ControlPlaneEffectJournalError(
            f"journal sequence mismatch: expected {expected_sequence}, got {entry.publication_sequence}"
        )
    if previous_entry is None:
        if entry.prior_journal_entry_id is not None or entry.prior_entry_digest is not None:
            raise ControlPlaneEffectJournalError("first journal entry cannot reference prior linkage")
    else:
        if entry.run_id != previous_entry.run_id:
            raise ControlPlaneEffectJournalError("journal append must stay within a single run")
        if entry.prior_journal_entry_id != previous_entry.journal_entry_id:
            raise ControlPlaneEffectJournalError("journal append prior_journal_entry_id mismatch")
        if entry.prior_entry_digest != previous_entry.entry_digest:
            raise ControlPlaneEffectJournalError("journal append prior_entry_digest mismatch")
    expected_digest = compute_effect_journal_entry_digest(entry)
    if entry.entry_digest != expected_digest:
        raise ControlPlaneEffectJournalError("journal entry digest mismatch")
    return True


def validate_effect_journal_chain(
    entries: Iterable["EffectJournalEntryRecord"],
) -> tuple["EffectJournalEntryRecord", ...]:
    ordered_entries = tuple(sorted(entries, key=lambda entry: entry.publication_sequence))
    previous_entry: EffectJournalEntryRecord | None = None
    for expected_sequence, entry in enumerate(ordered_entries, start=1):
        if entry.publication_sequence != expected_sequence:
            raise ControlPlaneEffectJournalError(
                f"journal chain is not contiguous at sequence {expected_sequence}"
            )
        validate_effect_journal_append(previous_entry=previous_entry, entry=entry)
        previous_entry = entry
    return ordered_entries


def validate_checkpoint_acceptance(
    checkpoint: "CheckpointRecord",
    acceptance: "CheckpointAcceptanceRecord",
    *,
    journal_entries: Iterable["EffectJournalEntryRecord"] = (),
    reservation_ids: Iterable[str] | None = None,
    lease_ids: Iterable[str] | None = None,
) -> bool:
    if acceptance.checkpoint_id != checkpoint.checkpoint_id:
        raise ControlPlaneCheckpointError("checkpoint acceptance must reference its parent checkpoint")
    if acceptance.outcome is CheckpointAcceptanceOutcome.REJECTED:
        return True
    if acceptance.evaluated_policy_digest != checkpoint.policy_digest:
        raise ControlPlaneCheckpointError("checkpoint acceptance policy digest mismatch")
    if acceptance.resumability_class is not checkpoint.resumability_class:
        raise ControlPlaneCheckpointError("checkpoint acceptance resumability mismatch")
    if checkpoint.dependent_effect_refs and not acceptance.dependent_effect_entry_refs:
        raise ControlPlaneCheckpointError("accepted checkpoint must publish dependent effect journal references")

    journal_entries = tuple(journal_entries)
    available_effect_ids = {entry.effect_id for entry in journal_entries}
    available_entry_ids = {entry.journal_entry_id for entry in journal_entries}
    missing_effect_ids = sorted(set(checkpoint.dependent_effect_refs) - available_effect_ids)
    if missing_effect_ids:
        raise ControlPlaneCheckpointError(
            f"checkpoint acceptance missing effect journal coverage for {missing_effect_ids!r}"
        )
    missing_entry_ids = sorted(set(acceptance.dependent_effect_entry_refs) - available_entry_ids)
    if missing_entry_ids:
        raise ControlPlaneCheckpointError(
            f"checkpoint acceptance references unknown journal entries {missing_entry_ids!r}"
        )

    if reservation_ids is not None:
        missing_reservation_ids = sorted(set(acceptance.dependent_reservation_refs) - set(reservation_ids))
        if missing_reservation_ids:
            raise ControlPlaneCheckpointError(
                f"checkpoint acceptance references unknown reservations {missing_reservation_ids!r}"
            )
    if lease_ids is not None:
        missing_lease_ids = sorted(set(acceptance.dependent_lease_refs) - set(lease_ids))
        if missing_lease_ids:
            raise ControlPlaneCheckpointError(
                f"checkpoint acceptance references unknown leases {missing_lease_ids!r}"
            )
    return True


__all__ = [
    "ControlPlaneCheckpointError",
    "ControlPlaneEffectJournalError",
    "compute_effect_journal_entry_digest",
    "create_effect_journal_entry",
    "validate_checkpoint_acceptance",
    "validate_effect_journal_append",
    "validate_effect_journal_chain",
]
