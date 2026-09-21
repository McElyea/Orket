from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.application.services.runtime_input_service import RuntimeInputService


class GiteaStateWorkerCoordinator:
    """
    Bounded coordinator loop for repeatedly invoking a GiteaStateWorker.
    """

    def __init__(
        self,
        *,
        worker: Any,
        fetch_limit: int = 5,
        max_iterations: int = 100,
        max_idle_streak: int = 10,
        max_duration_seconds: float = 60.0,
        idle_sleep_seconds: float = 0.0,
        runtime_inputs: RuntimeInputService | None = None,
    ):
        self.worker = worker
        self.fetch_limit = max(1, int(fetch_limit))
        self.max_iterations = max(1, int(max_iterations))
        self.max_idle_streak = max(1, int(max_idle_streak))
        self.max_duration_seconds = max(0.0, float(max_duration_seconds))
        self.idle_sleep_seconds = max(0.0, float(idle_sleep_seconds))
        self.runtime_inputs = RuntimeInputService() if runtime_inputs is None else runtime_inputs

    async def run(
        self,
        *,
        work_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        summary_out: str | Path | None = None,
    ) -> dict[str, Any]:
        summary_path = Path.cwd() / summary_out if summary_out is not None else None
        started = self.runtime_inputs.monotonic_seconds()
        iterations = 0
        consumed_count = 0
        idle_count = 0
        idle_streak = 0
        stop_reason = "max_iterations"

        while iterations < self.max_iterations:
            elapsed = self.runtime_inputs.monotonic_seconds() - started
            if elapsed >= self.max_duration_seconds:
                stop_reason = "max_duration_seconds"
                break

            consumed = bool(await self.worker.run_once(work_fn=work_fn, fetch_limit=self.fetch_limit))
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

        elapsed_ms = int((self.runtime_inputs.monotonic_seconds() - started) * 1000)
        summary = {
            "iterations": iterations,
            "consumed_count": consumed_count,
            "idle_count": idle_count,
            "stop_reason": stop_reason,
            "elapsed_ms": elapsed_ms,
        }
        if summary_path is not None:
            await run_owned_thread(partial(_write_summary, summary_path, json.dumps(summary, indent=2)),
                label="gitea-loop-summary-write")
        return summary


def _write_summary(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
