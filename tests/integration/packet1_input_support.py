"""Shared fixtures for integration proof of construction-bound Packet-1 inputs."""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tests.helpers.card_completion import complete_existing_card

ENVIRONMENT_A = {
    "ORKET_LLM_PROVIDER": "llama_cpp",
    "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "packet1-profile-a",
}
ENVIRONMENT_B = {
    "ORKET_LLM_PROVIDER": "lmstudio",
    "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "packet1-profile-b",
}
ENVIRONMENT_C = {
    "ORKET_LLM_PROVIDER": "ollama",
    "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID": "packet1-profile-c",
}
CONTROLLED_TELEMETRY = {
    "provider_backend": "openai_compat",
    "model": "packet1-controlled-model",
    "profile_id": "packet1-controlled-profile",
    "profile_resolution_path": "fallback",
    "retries": 0,
}
_PACKET1_ENVIRONMENT_KEYS = (
    "ORKET_LLM_PROVIDER",
    "ORKET_MODEL_PROVIDER",
    "ORKET_LOCAL_PROMPTING_PROFILE_ID",
    "ORKET_LOCAL_PROMPTING_FALLBACK_PROFILE_ID",
)


def set_packet1_environment(monkeypatch: Any, values: dict[str, str]) -> None:
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_ALLOW_FALLBACK", "true")
    for key in _PACKET1_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    for key, value in values.items():
        monkeypatch.setenv(key, value)


async def write_json(path: Path, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    content = json.dumps(payload, sort_keys=True)
    await asyncio.to_thread(path.write_text, content, encoding="utf-8")


async def read_json(path: Path) -> dict[str, Any]:
    content = await asyncio.to_thread(path.read_bytes)
    return json.loads(content.decode("utf-8"))


async def write_epic_assets(root: Path, epic_id: str) -> None:
    await write_json(
        root / "model" / "core" / "teams" / "standard.json",
        {"name": "standard", "seats": {"lead_architect": {"name": "Lead", "roles": ["lead_architect"]}}},
    )
    await write_json(
        root / "model" / "core" / "epics" / f"{epic_id}.json",
        {
            "id": epic_id,
            "name": epic_id,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Packet-1 construction-input capture",
            "params": {},
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": [{
                "id": "ISSUE-1",
                "summary": "Record controlled Packet-1 telemetry",
                "seat": "lead_architect",
                "priority": "High",
                "depends_on": [],
            }],
        },
    )


async def run_controlled_packet1(
    pipeline: Any,
    monkeypatch: Any,
    *,
    workspace: Path,
    epic_id: str,
    run_id: str,
    telemetry: dict[str, Any] | None,
    after_start: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Run real publication/ledger paths with only model work controlled."""
    started_packet1: dict[str, Any] = {}

    async def execute_controlled_model(**kwargs: Any) -> None:
        started = await pipeline.run_ledger.get_run(str(kwargs["run_id"]))
        assert started is not None
        started_packet1.update(started["artifact_json"]["packet1_facts"])
        if after_start is not None:
            after_start()
        if telemetry is not None:
            await write_json(
                workspace / "observability" / run_id / "ISSUE-1" / "001_lead_architect" / "model_response_raw.json",
                telemetry,
            )
        await complete_existing_card(
            pipeline.async_cards,
            "ISSUE-1",
            workspace,
            service=pipeline.runtime_context.card_completion,
        )

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", execute_controlled_model)
    await pipeline.run_epic(epic_id, build_id=f"build-{epic_id}", session_id=run_id)
    ledger = await pipeline.run_ledger.get_run(run_id)
    assert ledger is not None
    summary_path = Path(ledger["artifact_json"]["run_summary_path"])
    return {
        "started": dict(started_packet1),
        "ledger": ledger,
        "summary": ledger["summary_json"],
        "physical": await read_json(summary_path),
        "summary_path": summary_path,
    }
