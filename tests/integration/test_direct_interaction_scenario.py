"""Actual direct scenario command publishes verified artifacts and exits cleanly."""
import asyncio
import json
from pathlib import Path

import pytest

from tests.integration.test_runtime_entrypoints import child

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
SCRIPT = Path(__file__).resolve().parents[2] / "scripts/streaming/run_provider_scenario_direct.py"


@pytest.mark.parametrize("cancel", [False, True])
async def test_direct_stub_scenario_finishes_owned_interaction_before_success(tmp_path, cancel):
    scenario = {"scenario_id": "owned-stub", "runtime_env": {"ORKET_MODEL_STREAM_PROVIDER": "stub"},
                "turn": {"input_config": {"seed": 9, "first_token_delay_ms": 30}},
                "expect": {"require_commit_final": True}}
    if cancel:
        scenario["turn"]["cancel_at"] = {"event_type": "model_loading", "after_count": 1}
    path = tmp_path / "scenario.json"
    await asyncio.to_thread(path.write_text, json.dumps(scenario), encoding="utf-8")
    code, output, error = await child(tmp_path, [str(SCRIPT), "--scenario", str(path), "--timeout", "3"])
    assert code == 0 and "PASS scenario=owned-stub" in output, output + error
    commits = await asyncio.to_thread(lambda: list(tmp_path.rglob("authority_commit.json")))
    assert len(commits) == 1
    payload = json.loads(await asyncio.to_thread(commits[0].read_text, encoding="utf-8"))
    assert payload["authoritative"] is True
    assert await asyncio.to_thread(commits[0].with_name("interaction_trace.jsonl").is_file)
    assert ("terminal=turn_interrupted" if cancel else "terminal=turn_final") in output
    before = await asyncio.to_thread(commits[0].read_bytes)
    await asyncio.sleep(0.05)
    assert await asyncio.to_thread(commits[0].read_bytes) == before
