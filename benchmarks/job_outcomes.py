"""Follow admissions to retained acceptance; HTTP success is never completion."""
from __future__ import annotations

import asyncio
import time

import httpx


async def observe_job(client: httpx.AsyncClient, base_url: str, headers: dict, *,
                      asset_id: str, expected_missing: bool, deadline_seconds: float) -> dict:
    start = time.perf_counter()
    row = {"asset_id": asset_id, "outcome": "unobserved", "completion_accepted": False}
    try:
        response = await client.post(f"{base_url}/v1/system/run-active", json={"issue_id": asset_id}, headers=headers)
        row["http_status"] = response.status_code
        if expected_missing:
            row["outcome"] = "missing_target_rejected" if response.status_code == 404 else "unexpected_admission"
            return row
        if response.status_code != 200:
            row["outcome"] = "admission_rejected"
            return row
        session = response.json()["session_id"]
        row["session_id"] = session
        while time.perf_counter() - start < deadline_seconds:
            result = await client.get(f"{base_url}/v1/runs/{session}/view", headers=headers)
            if result.status_code == 200:
                view = result.json()
                row.update(raw_status=view.get("raw_status"), completion_accepted=view.get("completion_accepted") is True,
                           completion_rejection=view.get("completion_rejection"))
                if row["completion_accepted"]:
                    row["outcome"] = "accepted_completion"
                    return row
                if row["raw_status"] in {"done", "completed", "failed", "blocked", "canceled", "cancelled"}:
                    row["outcome"] = "terminal_unaccepted"
                    return row
            elif result.status_code != 404:
                result.raise_for_status()
            await asyncio.sleep(0.2)
        row["outcome"] = "terminal_observation_timeout"
    except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
        row.update(outcome="observation_error", error_type=type(exc).__name__, error=str(exc))
    finally:
        row["duration_ms"] = (time.perf_counter() - start) * 1000
    return row
