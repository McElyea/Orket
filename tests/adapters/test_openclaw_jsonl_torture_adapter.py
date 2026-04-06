from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from orket.adapters.execution.openclaw_jsonl_adapter import OpenClawJsonlSubprocessAdapter


# Layer: integration
@pytest.mark.asyncio
async def test_openclaw_torture_adapter_serves_corpus_cases() -> None:
    adapter = OpenClawJsonlSubprocessAdapter(
        command=[sys.executable, "tools/fake_openclaw_adapter_torture.py"],
        io_timeout_seconds=10.0,
    )
    responses = await adapter.run_requests(
        [
            {"type": "next_attack", "case_id": "prompt_injection_direct_scope_violation"},
            {"type": "next_attack", "case_id": "autonomy_credentialed_action_requires_approval"},
        ]
    )
    assert len(responses) == 2
    assert responses[0]["type"] == "action_proposal"
    assert responses[0]["scenario_kind"] == "prompt_injection_direct_scope_violation"
    assert responses[0]["proposal"]["payload"]["scope_violation"] is True

    assert responses[1]["scenario_kind"] == "autonomy_credentialed_action_requires_approval"
    assert responses[1]["proposal"]["payload"]["approval_required_credentialed"] is True
    assert responses[1]["token_request"]["tool_name"] == "demo.credentialed_echo"


# Layer: unit
def test_openclaw_torture_adapter_select_case_id_returns_empty_on_empty_corpus() -> None:
    module_path = Path("tools/fake_openclaw_adapter_torture.py").resolve()
    spec = importlib.util.spec_from_file_location("fake_openclaw_adapter_torture", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module._select_case_id({}, []) == ""
