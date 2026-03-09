from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Sync capability methods may execute inside async workloads.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()
