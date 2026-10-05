"""Bounded selected-server diagnostics; preserve occupancy, TTFT and typed errors."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger


async def slots(client: httpx.AsyncClient, root: str) -> dict:
    try:
        response = await client.get(root + "/slots")
        response.raise_for_status()
        rows = response.json()
        return {"available": True, "slots": [{key: row.get(key) for key in
                ("id", "id_task", "is_processing", "n_ctx")} for row in rows]}
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return {"available": False, "error_type": type(exc).__name__}


async def diagnose(base_url: str, model: str, repetitions: int, output: Path) -> int:
    root = base_url.rstrip("/").removesuffix("/v1")
    report = {"model": model, "base_url": base_url, "proof_mode": "live direct provider diagnostic",
              "scope": "No server restart or model switch; read timeout matches runtime's ten-second cap", "requests": []}
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
        for index in range(repetitions):
            before = await slots(client, root)
            row = {"iteration": index + 1, "before": before, "first_token_ms": None, "content_deltas": 0}
            report["requests"].append(row)
            if (not before["available"] or not before["slots"]
                    or any(slot["is_processing"] is not False for slot in before["slots"])):
                row.update(observed_path="blocked", observed_result="environment blocker", reason="idle_slot_unconfirmed")
                break
            start = time.perf_counter()
            try:
                async with client.stream("POST", base_url.rstrip("/") + "/chat/completions", json={"model": model,
                    "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": 1, "stream": True}) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        chunk = json.loads(line.removeprefix("data: "))
                        for choice in chunk.get("choices", []):
                            delta = choice.get("delta", {})
                            if delta.get("content") or delta.get("reasoning_content"):
                                row["content_deltas"] += 1
                                if row["first_token_ms"] is None:
                                    row["first_token_ms"] = (time.perf_counter() - start) * 1000
                row.update(observed_path="primary", observed_result="success" if row["content_deltas"] else "failure")
            except (httpx.HTTPError, OSError, ValueError) as exc:
                row.update(observed_path="primary", observed_result="failure", error_type=type(exc).__name__, error=str(exc))
            row["wall_ms"] = (time.perf_counter() - start) * 1000
            row["after"] = await slots(client, root)
            write_payload_with_diff_ledger(output, report)
            if row["observed_result"] != "success":
                break
    write_payload_with_diff_ledger(output, report)
    print(json.dumps(report))
    return 0 if len(report["requests"]) == repetitions and all(
        row["observed_result"] == "success" for row in report["requests"]) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--out", type=Path, default=Path("benchmarks/staging/General/llama_stream_diagnostic.json"))
    args = parser.parse_args()
    endpoint = urlsplit(args.base_url)
    if (endpoint.scheme != "http" or endpoint.hostname not in {"localhost", "127.0.0.1", "::1"}
            or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment):
        parser.error("Use the selected local HTTP server without URL credentials, queries or fragments")
    if not 1 <= args.repetitions <= 20:
        parser.error("--repetitions must be between 1 and 20")
    return asyncio.run(diagnose(args.base_url, args.model, args.repetitions, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
