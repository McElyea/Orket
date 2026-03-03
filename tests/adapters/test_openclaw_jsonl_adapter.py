from __future__ import annotations

import sys

import pytest

from orket.adapters.execution.openclaw_jsonl_adapter import OpenClawJsonlSubprocessAdapter


@pytest.mark.asyncio
async def test_openclaw_jsonl_subprocess_adapter_runs_stub_end_to_end() -> None:
    adapter = OpenClawJsonlSubprocessAdapter(
        command=[sys.executable, "tools/fake_openclaw_adapter_strict.py"],
        io_timeout_seconds=10.0,
    )

    responses = await adapter.run_requests(
        [
            {"type": "next_action", "scenario_kind": "blocked_destructive"},
            {"type": "next_action", "scenario_kind": "approval_required"},
            {"type": "next_action", "scenario_kind": "credentialed_token"},
            {"type": "next_action", "scenario_kind": "credentialed_token_replay"},
        ]
    )

    assert len(responses) == 4
    assert responses[0]["type"] == "action_proposal"
    assert responses[0]["scenario_kind"] == "blocked_destructive"
    assert responses[0]["proposal"]["payload"]["scope_violation"] is True
    assert responses[1]["proposal"]["payload"]["approval_required_destructive"] is True
    assert responses[2]["proposal"]["payload"]["approval_required_credentialed"] is True
    assert responses[2]["token_request"]["tool_name"] == "demo.credentialed_echo"
    assert responses[3]["scenario_kind"] == "credentialed_token_replay"
