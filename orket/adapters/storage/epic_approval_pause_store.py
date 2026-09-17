"""Pause history shares the epic journal transaction and admission serialization."""
from __future__ import annotations

import aiosqlite

from orket.core.contracts.epic_approval_pause import EpicApprovalPause
from orket.core.contracts.epic_approval_recovery import (
    EPIC_CONTINUATION_LOCK_ARTIFACT,
    EpicApprovalRecovery,
    EpicContinuationLockRef,
    approval_claim_transition_allowed,
)


class EpicApprovalPauseStore:
    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection, session_id: str):
        self.connection, self.session_id = connection, session_id

    async def latest(self) -> EpicApprovalPause | None:
        previous = None
        async with self.connection.execute(
            "SELECT sequence, payload, digest FROM epic_approval_pauses WHERE session_id = ? ORDER BY sequence",
            (self.session_id,),
        ) as cursor:
            async for sequence, payload, digest in cursor:
                record = EpicApprovalPause.model_validate_json(payload)
                marker = record.artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT)
                if marker is not None and EpicContinuationLockRef.model_validate(marker).session_id != self.session_id:
                    raise ValueError("E_EPIC_APPROVAL_PAUSE_LOCK_CONFLICT")
                if (record.session_id != self.session_id or record.sequence != sequence or record.digest() != digest
                        or sequence != (previous.sequence + 1 if previous else 1)
                        or (previous and not self._next_pause(previous, record))):
                    raise ValueError("E_EPIC_APPROVAL_PAUSE_INTEGRITY")
                previous = record
        return previous

    async def save(self, record: EpicApprovalPause) -> None:
        record = EpicApprovalPause.model_validate_json(record.model_dump_json())
        prior = await self.latest()
        if record.session_id != self.session_id:
            raise ValueError("E_EPIC_APPROVAL_PAUSE_SESSION")
        if prior == record:
            return
        if prior is None:
            valid = record.sequence == 1 and record.phase == "waiting"
        elif record.sequence == prior.sequence:
            valid = approval_claim_transition_allowed(prior, record)
        else:
            valid = record.phase == "waiting" and self._next_pause(prior, record)
        if not valid:
            raise ValueError("E_EPIC_APPROVAL_PAUSE_CONFLICT")
        await self.connection.execute(
            "INSERT INTO epic_approval_pauses(session_id, sequence, payload, digest) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(session_id, sequence) DO UPDATE SET payload=excluded.payload, digest=excluded.digest",
            (self.session_id, record.sequence, record.model_dump_json(), record.digest()))

    async def recoveries(self) -> list[EpicApprovalRecovery]:
        await self.latest()  # Recovery cannot conceal a gap in the original pause history.
        records, heads, request_ids = [], {}, set()
        async with self.connection.execute(
            "SELECT sequence, ordinal, request_id, payload, digest FROM epic_approval_recoveries "
            "WHERE session_id = ? ORDER BY sequence, ordinal", (self.session_id,),
        ) as cursor:
            async for sequence, ordinal, request_id, payload, digest in cursor:
                record = EpicApprovalRecovery.model_validate_json(payload)
                prior = heads.get(sequence)
                if (record.request.session_id != self.session_id or record.request.sequence != sequence
                        or record.ordinal != ordinal or record.request.request_id != request_id
                        or request_id in request_ids or record.digest() != digest
                        or ordinal != (prior.ordinal + 1 if prior else 1)
                        or record.request.expected_recovery_digest != (prior.digest() if prior else None)):
                    raise ValueError("E_EPIC_APPROVAL_RECOVERY_HISTORY")
                await self._validate_recovery_pause(record)
                records.append(record)
                heads[sequence] = record
                request_ids.add(request_id)
        return records

    async def save_recovery(self, record: EpicApprovalRecovery) -> None:
        record = EpicApprovalRecovery.model_validate_json(record.model_dump_json())
        records = await self.recoveries()
        matches = [row for row in records if row.request.request_id == record.request.request_id]
        if matches:
            if matches[0] != record:
                raise ValueError("E_EPIC_APPROVAL_RECOVERY_REQUEST_CONFLICT")
            return
        previous = [row for row in records if row.request.sequence == record.request.sequence]
        prior = previous[-1] if previous else None
        if (record.request.session_id != self.session_id or record.ordinal != (prior.ordinal + 1 if prior else 1)
                or record.request.expected_recovery_digest != (prior.digest() if prior else None)):
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_HISTORY")
        await self._validate_recovery_pause(record)
        await self.connection.execute(
            "INSERT INTO epic_approval_recoveries(session_id, sequence, ordinal, request_id, payload, digest) "
            "VALUES (?, ?, ?, ?, ?, ?)", (self.session_id, record.request.sequence, record.ordinal,
                                          record.request.request_id, record.model_dump_json(), record.digest()))
        if record not in await self.recoveries():
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_UNCONFIRMED")

    async def _validate_recovery_pause(self, record: EpicApprovalRecovery) -> None:
        row = await (await self.connection.execute(
            "SELECT payload, digest FROM epic_approval_pauses WHERE session_id = ? AND sequence = ?",
            (self.session_id, record.request.sequence))).fetchone()
        if row is None:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_PAUSE_MISSING")
        pause = EpicApprovalPause.model_validate_json(row[0])
        if (pause.session_id != self.session_id or pause.sequence != record.request.sequence or pause.phase != "claimed"
                or pause.digest() != row[1] or pause.digest() != record.request.expected_pause_digest
                or pause.artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT) != record.lock.model_dump(mode="json")):
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_PAUSE_CONFLICT")

    @staticmethod
    def _next_pause(prior: EpicApprovalPause, record: EpicApprovalPause) -> bool:
        return (prior.phase == "claimed" and record.sequence == prior.sequence + 1 and prior.request == record.request
                and prior.export_binding == record.export_binding and prior.epic_asset == record.epic_asset
                and prior.model_override == record.model_override
                and all(record.approvals.get(key) == value for key, value in prior.approvals.items()))
