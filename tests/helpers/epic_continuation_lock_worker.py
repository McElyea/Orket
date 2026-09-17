"""Own an actual native continuation lock until release or process death."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from orket.adapters.storage.epic_continuation_lock import EpicContinuationLocks


async def main():
    async with EpicContinuationLocks(Path(sys.argv[1])).hold(sys.argv[2]) as reference:
        print(json.dumps({"barrier": "continuation_lock_held", "reference": reference.model_dump(mode="json")}), flush=True)
        if (await asyncio.to_thread(sys.stdin.readline)).strip() != "release":
            raise ValueError("Expected explicit fixture release")


if __name__ == "__main__":
    asyncio.run(main())
