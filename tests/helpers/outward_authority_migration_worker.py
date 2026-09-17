"""Native acceptance worker stopped after an uncommitted adoption/event write."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.outward_authority_migration_service import OutwardAuthorityMigrationService


async def main():
    database, run_id, digest, marker, phase = sys.argv[1:]
    original = OutwardStoreTransaction.append_event

    async def hold_after_append(transaction, event):
        result = await original(transaction, event)
        if event.event_type == phase:
            await asyncio.to_thread(Path(marker).write_text, "uncommitted", encoding="utf-8")
            await asyncio.Event().wait()
        return result

    OutwardStoreTransaction.append_event = hold_after_append
    try:
        await OutwardAuthorityMigrationService(Path(database)).migrate(
            run_id, expected_run_digest=digest, actor_ref="native-migration-proof", owners_stopped=True,
        )
    finally:
        OutwardStoreTransaction.append_event = original


if __name__ == "__main__":
    asyncio.run(main())
