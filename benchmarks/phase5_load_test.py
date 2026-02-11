from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import httpx
import websockets


@dataclass
class LoadResult:
    durations_ms: List[float]
    failures: int

    def summary(self, name: str) -> str:
        if not self.durations_ms:
            return f"{name}: no samples"
        p50 = statistics.median(self.durations_ms)
        p95 = percentile(self.durations_ms, 95)
        p99 = percentile(self.durations_ms, 99)
        err_rate = (self.failures / (len(self.durations_ms) + self.failures)) * 100
        return (
            f"{name}: n={len(self.durations_ms)} failures={self.failures} "
            f"p50={p50:.1f}ms p95={p95:.1f}ms p99={p99:.1f}ms error_rate={err_rate:.2f}%"
        )

    def as_dict(self) -> Dict[str, Any]:
        if not self.durations_ms:
            return {
                "samples": 0,
                "failures": self.failures,
                "p50_ms": None,
                "p95_ms": None,
                "p99_ms": None,
                "error_rate_percent": 100.0 if self.failures else 0.0,
            }
        err_rate = (self.failures / (len(self.durations_ms) + self.failures)) * 100
        return {
            "samples": len(self.durations_ms),
            "failures": self.failures,
            "p50_ms": round(statistics.median(self.durations_ms), 3),
            "p95_ms": round(percentile(self.durations_ms, 95), 3),
            "p99_ms": round(percentile(self.durations_ms, 99), 3),
            "error_rate_percent": round(err_rate, 4),
        }


def percentile(values: List[float], p: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(len(ordered) * (p / 100.0)) - 1))
    return ordered[idx]


async def _timed_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    expected_statuses: Optional[set[int]] = None,
    **kwargs
) -> tuple[float, bool]:
    start = time.perf_counter()
    try:
        response = await client.request(method, url, **kwargs)
        if expected_statuses is None:
            ok = 200 <= response.status_code < 300
        else:
            ok = response.status_code in expected_statuses
    except (httpx.HTTPError, OSError):
        ok = False
    duration_ms = (time.perf_counter() - start) * 1000
    return duration_ms, ok


async def run_webhook_load(base_url: str, total: int, concurrency: int) -> LoadResult:
    sem = asyncio.Semaphore(concurrency)
    durations: List[float] = []
    failures = 0
    payload = {
        "event": "test",
        "action": "opened",
        "payload": {"repository": {"full_name": "local/test"}},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker(i: int):
            nonlocal failures
            async with sem:
                duration_ms, ok = await _timed_request(
                    client,
                    "POST",
                    f"{base_url}/webhook/test",
                    json=payload,
                    expected_statuses={200},
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
                duration_ms, ok = await _timed_request(
                    client,
                    "GET",
                    f"{base_url}/v1/system/heartbeat",
                    expected_statuses={200},
                )
                durations.append(duration_ms)
                if not ok:
                    failures += 1

        await asyncio.gather(*(worker(i) for i in range(total)))
    return LoadResult(durations, failures)


async def run_parallel_epic_trigger_load(base_url: str, total: int, concurrency: int) -> LoadResult:
    sem = asyncio.Semaphore(concurrency)
    durations: List[float] = []
    failures = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        async def worker(i: int):
            nonlocal failures
            async with sem:
                duration_ms, ok = await _timed_request(
                    client,
                    "POST",
                    f"{base_url}/v1/system/run-active",
                    json={"issue_id": f"LOAD-EPIC-{i}"},
                    expected_statuses={200},
                )
                durations.append(duration_ms)
                if not ok:
                    failures += 1

        await asyncio.gather(*(worker(i) for i in range(total)))
    return LoadResult(durations, failures)


async def run_websocket_load(ws_url: str, clients: int) -> LoadResult:
    durations: List[float] = []
    failures = 0

    async def connect_worker(i: int):
        nonlocal failures
        start = time.perf_counter()
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(f"ping-{i}")
                await asyncio.sleep(0.05)
            durations.append((time.perf_counter() - start) * 1000)
        except (OSError, websockets.exceptions.WebSocketException, asyncio.TimeoutError):
            failures += 1

    await asyncio.gather(*(connect_worker(i) for i in range(clients)))
    return LoadResult(durations, failures)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 load-test harness")
    parser.add_argument("--webhook-base-url", default="http://127.0.0.1:8080", help="Webhook server base URL")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8082", help="API server base URL")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8082/ws/events", help="WebSocket URL")
    parser.add_argument("--webhook-total", type=int, default=100)
    parser.add_argument("--webhook-concurrency", type=int, default=25)
    parser.add_argument("--api-total", type=int, default=200)
    parser.add_argument("--api-concurrency", type=int, default=50)
    parser.add_argument("--epic-total", type=int, default=10)
    parser.add_argument("--epic-concurrency", type=int, default=10)
    parser.add_argument("--ws-clients", type=int, default=50)
    parser.add_argument("--out", default="", help="Optional JSON result output path")
    args = parser.parse_args()

    webhook_result = await run_webhook_load(args.webhook_base_url, args.webhook_total, args.webhook_concurrency)
    api_result = await run_api_load(args.api_base_url, args.api_total, args.api_concurrency)
    epic_result = await run_parallel_epic_trigger_load(args.api_base_url, args.epic_total, args.epic_concurrency)
    ws_result = await run_websocket_load(args.ws_url, args.ws_clients)

    print(webhook_result.summary("webhook"))
    print(api_result.summary("api_heartbeat"))
    print(epic_result.summary("parallel_epic_trigger"))
    print(ws_result.summary("websocket_connect"))

    payload = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "config": {
            "webhook_base_url": args.webhook_base_url,
            "api_base_url": args.api_base_url,
            "ws_url": args.ws_url,
            "webhook_total": args.webhook_total,
            "webhook_concurrency": args.webhook_concurrency,
            "api_total": args.api_total,
            "api_concurrency": args.api_concurrency,
            "epic_total": args.epic_total,
            "epic_concurrency": args.epic_concurrency,
            "ws_clients": args.ws_clients,
        },
        "results": {
            "webhook": webhook_result.as_dict(),
            "api_heartbeat": api_result.as_dict(),
            "parallel_epic_trigger": epic_result.as_dict(),
            "websocket_connect": ws_result.as_dict(),
        },
    }
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
