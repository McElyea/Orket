from __future__ import annotations
import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import List

import httpx


@dataclass
class LoadResult:
    durations_ms: List[float]
    failures: int

    def summary(self, name: str) -> str:
        if not self.durations_ms:
            return f"{name}: no samples"
        p50 = statistics.median(self.durations_ms)
        p95 = sorted(self.durations_ms)[int(len(self.durations_ms) * 0.95) - 1]
        p99 = sorted(self.durations_ms)[int(len(self.durations_ms) * 0.99) - 1]
        err_rate = (self.failures / (len(self.durations_ms) + self.failures)) * 100
        return (
            f"{name}: n={len(self.durations_ms)} failures={self.failures} "
            f"p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms error_rate={err_rate:.2f}%"
        )


async def _timed_request(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> tuple[float, bool]:
    start = time.perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        ok = response.status_code < 500
    except Exception:
        ok = False
    duration_ms = (time.perf_counter() - start) * 1000
    return duration_ms, ok


async def run_webhook_load(base_url: str, total: int, concurrency: int) -> LoadResult:
    sem = asyncio.Semaphore(concurrency)
    durations: List[float] = []
    failures = 0
    payload = {"event": "test", "action": "opened", "repository": {"full_name": "local/test"}}

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker(i: int):
            nonlocal failures
            async with sem:
                duration_ms, ok = await _timed_request(
                    client,
                    "POST",
                    f"{base_url}/webhook/test",
                    json=payload,
                )
                durations.append(duration_ms)
                if not ok:
                    failures += 1

        await asyncio.gather(*(worker(i) for i in range(total)))
    return LoadResult(durations, failures)


async def run_api_load(base_url: str, total: int, concurrency: int) -> LoadResult:
    sem = asyncio.Semaphore(concurrency)
    durations: List[float] = []
    failures = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker(i: int):
            nonlocal failures
            async with sem:
                duration_ms, ok = await _timed_request(client, "GET", f"{base_url}/v1/system/heartbeat")
                durations.append(duration_ms)
                if not ok:
                    failures += 1

        await asyncio.gather(*(worker(i) for i in range(total)))
    return LoadResult(durations, failures)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 load-test harness")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Server base URL")
    parser.add_argument("--webhook-total", type=int, default=100)
    parser.add_argument("--webhook-concurrency", type=int, default=25)
    parser.add_argument("--api-total", type=int, default=200)
    parser.add_argument("--api-concurrency", type=int, default=50)
    args = parser.parse_args()

    webhook_result = await run_webhook_load(args.base_url, args.webhook_total, args.webhook_concurrency)
    api_result = await run_api_load(args.base_url, args.api_total, args.api_concurrency)

    print(webhook_result.summary("webhook"))
    print(api_result.summary("api_heartbeat"))


if __name__ == "__main__":
    asyncio.run(main())
