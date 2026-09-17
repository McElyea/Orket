"""Native cooperating writer, with a bounded physical admission barrier."""
import asyncio
import json
import sys
from pathlib import Path

# Direct invocation from a foreign cwd still needs the copied test support.
# Installed acceptance copies no core package into this support root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import orket
from orket.adapters.storage.protocol_ledger_io import owned_protocol_io
from orket.core.contracts.local_file_lock import LocalFileLockError
from tests.helpers.dual_ledger import CommittedHeldSQLite, repositories, start_values


async def main():
    root, database, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    core_origin = str(await owned_protocol_io(Path(orket.__file__).resolve))
    repo = repositories(root, database=database, **({"sqlite_type": CommittedHeldSQLite} if mode == "hold" else {}))
    repo._telemetry.sink = lambda _: None
    try:
        if mode == "hold":
            task = asyncio.create_task(repo.start_run(**start_values()))
            await asyncio.wait_for(repo.sqlite_repo.entered.wait(), 10)
            await owned_protocol_io((root / "owner.ready").write_text, "ready", encoding="utf-8")
            try:
                async with asyncio.timeout(15):
                    # An independent parent process releases this physical-file barrier.
                    while not await owned_protocol_io((root / "owner.release").exists):  # noqa: ASYNC110
                        await asyncio.sleep(0.01)
            finally:
                repo.sqlite_repo.release.set()
                await task
        else:
            await repo.start_run(**start_values())
        print(json.dumps({"status": "success", "core_origin": core_origin,
                          "pending": await repo._load_intents(),
                          "events": [r["kind"] for r in await repo.list_events("run")]}))
        return 0
    except LocalFileLockError as exc:
        print(json.dumps({"status": "busy", "core_origin": core_origin, "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
