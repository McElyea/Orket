from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict


class GiteaStateWorkerCoordinator:
    """
    Bounded coordinator loop for repeatedly invoking a GiteaStateWorker.
    """

    def __init__(
        self,
        *,
        worker: Any,
        max_iterations: int = 100,
        max_idle_streak: int = 10,
        max_duration_seconds: float = 60.0,
        idle_sleep_seconds: float = 0.0,
    ):
        self.worker = worker
        self.max_iterations = max(1, int(max_iterations))
        self.max_idle_streak = max(1, int(max_idle_streak))
        self.max_duration_seconds = max(0.0, float(max_duration_seconds))
        self.idle_sleep_seconds = max(0.0, float(idle_sleep_seconds))

    async def run(
        self,
        *,
        work_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        started = time.monotonic()
        iterations = 0
        consumed_count = 0
        idle_count = 0
        idle_streak = 0
        stop_reason = "max_iterations"

        while iterations < self.max_iterations:
            elapsed = time.monotonic() - started
            if elapsed >= self.max_duration_seconds:
                stop_reason = "max_duration_seconds"
                break

            consumed = bool(await self.worker.run_once(work_fn=work_fn))
            iterations += 1

            if consumed:
                consumed_count += 1
                idle_streak = 0
                continue

            idle_count += 1
            idle_streak += 1
            if idle_streak >= self.max_idle_streak:
                stop_reason = "max_idle_streak"
                break
            if self.idle_sleep_seconds > 0:
                await asyncio.sleep(self.idle_sleep_seconds)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "iterations": iterations,
            "consumed_count": consumed_count,
            "idle_count": idle_count,
            "stop_reason": stop_reason,
            "elapsed_ms": elapsed_ms,
        }
