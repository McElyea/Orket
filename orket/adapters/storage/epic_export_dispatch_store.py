"""Export owner records share the existing epic publication writer transaction."""
from __future__ import annotations

import aiosqlite

from orket.core.contracts.epic_export_recovery import EpicExportDispatch, export_dispatch_transition_allowed


class EpicExportDispatchStore:
    side_effecting = True

    def __init__(self, connection: aiosqlite.Connection, session_id: str):
        self.connection, self.session_id = connection, session_id

    async def get(self) -> EpicExportDispatch | None:
        row = await (await self.connection.execute(
            "SELECT payload, digest FROM epic_export_dispatches WHERE session_id = ?", (self.session_id,))).fetchone()
        if row is None:
            return None
        record = EpicExportDispatch.model_validate_json(row[0])
        if record.session_id != self.session_id or record.digest() != row[1]:
            raise ValueError("E_EPIC_EXPORT_DISPATCH_INTEGRITY")
        return record

    async def save(self, record: EpicExportDispatch) -> None:
        record = EpicExportDispatch.model_validate_json(record.model_dump_json())
        if record.session_id != self.session_id:
            raise ValueError("E_EPIC_EXPORT_DISPATCH_SESSION")
        prior = await self.get()
        if prior is None and (record.phase != "claimed" or record.fencing_generation != 1):
            raise ValueError("E_EPIC_EXPORT_DISPATCH_INITIAL_CLAIM_REQUIRED")
        if prior is not None and not export_dispatch_transition_allowed(prior, record):
            raise ValueError("E_EPIC_EXPORT_DISPATCH_CONFLICT")
        if prior == record:
            return
        await self.connection.execute(
            "INSERT INTO epic_export_dispatches(session_id, payload, digest) VALUES (?, ?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET payload=excluded.payload, digest=excluded.digest",
            (record.session_id, record.model_dump_json(), record.digest()))
        if await self.get() != record:
            raise ValueError("E_EPIC_EXPORT_DISPATCH_UNCONFIRMED")
