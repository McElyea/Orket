"""Bind explicit continuation grants to immutable pause and recovery history."""
from __future__ import annotations

from orket.core.contracts.epic_approval_recovery import (
    EPIC_APPROVAL_RECOVERY_ARTIFACT,
    EPIC_CONTINUATION_LOCK_ARTIFACT,
    EpicApprovalRecovery,
    EpicContinuationLockRef,
    approval_recovery_action,
)


async def inspect_approval_recovery(tx, request, publication_request, export_binding):
    pause = await tx.approval_pauses.latest()
    if (pause is None or pause.phase != "claimed" or pause.session_id != request.session_id
            or pause.sequence != request.sequence or pause.digest() != request.expected_pause_digest
            or pause.request != publication_request or pause.export_binding != export_binding):
        raise ValueError("E_EPIC_APPROVAL_RECOVERY_PAUSE_CONFLICT")
    marker = pause.artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT)
    if marker is None:
        raise ValueError("E_EPIC_APPROVAL_RECOVERY_LOCK_MISSING")
    lock = EpicContinuationLockRef.model_validate(marker)
    records = await tx.approval_pauses.recoveries()
    matches = [record for record in records if record.request.request_id == request.request_id]
    current = [record for record in records if record.request.sequence == pause.sequence]
    if matches:
        if matches[0].request != request:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_REQUEST_CONFLICT")
        if not current or matches[0] != current[-1]:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_SUPERSEDED")
        return pause, lock, current, True
    if request.expected_recovery_digest != (current[-1].digest() if current else None):
        raise ValueError("E_EPIC_APPROVAL_RECOVERY_HEAD_CONFLICT")
    if await tx.get_outcome() is not None or await tx.get_preparation() is not None or await tx.get() is not None:
        raise ValueError("E_EPIC_APPROVAL_RECOVERY_NOT_PENDING")
    return pause, lock, current, False


async def retain_approval_recovery(tx, *, request, lock, current, at):
    record = EpicApprovalRecovery(
        ordinal=len(current) + 1, request=request, lock=lock, decided_at=at,
        action=approval_recovery_action(request, lock, at))
    await tx.approval_pauses.save_recovery(record)


async def validate_approval_recovery_artifacts(tx, artifacts):
    records = await tx.approval_pauses.recoveries()
    expected = [record.reference() for record in records]
    observed = artifacts.get(EPIC_APPROVAL_RECOVERY_ARTIFACT)
    if observed != (expected if expected else None):
        raise ValueError("E_EPIC_APPROVAL_RECOVERY_EVIDENCE_CONFLICT")
