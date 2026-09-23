# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.extensions.runtime import ExtensionEngineAdapter
from scripts.security.build_tool_gate_audit import main

pytestmark = pytest.mark.integration


def test_build_tool_gate_audit_writes_diff_ledger_payload(tmp_path: Path) -> None:
    """Layer: integration. Verifies the canonical tool gate audit script writes a stable diff-ledger artifact."""
    out_path = tmp_path / "tool_gate_audit.json"

    exit_code = main(["--out", str(out_path), "--strict"])

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "tool_gate_audit.v1"
    assert payload["gate_surface"] == "governed_turn_tool_gate_v1"
    assert isinstance(payload.get("paths"), list)
    assert any(path["dispatch_path"] == "run_card.turn_executor.tool_dispatcher" for path in payload["paths"])
    assert any(path["dispatch_path"] == "extension_engine_action_normalized_run_card" for path in payload["paths"])
    assert any(path["dispatch_path"] == "agent_run_direct_tool_execution" for path in payload["paths"])
    by_dispatch = {row["dispatch_path"]: row for row in payload["paths"]}
    for name in ("direct_turn_executor_execute_turn", "direct_tool_dispatcher_execute_tools"):
        assert by_dispatch[name]["observed_result"] == "blocked"
        assert by_dispatch[name]["side_effect_observed"] is False
    assert isinstance(payload.get("diff_ledger"), list)


def test_tool_gate_audit_cannot_publish_after_required_engine_close_fails(tmp_path, monkeypatch):
    """Layer: integration. Required cleanup failure prevents a passing audit artifact."""
    original = ExtensionEngineAdapter.close

    async def refuse(self):
        await original(self)
        raise OSError("controlled audit engine close failure")

    monkeypatch.setattr(ExtensionEngineAdapter, "close", refuse)
    output = tmp_path / "failed-audit.json"
    with pytest.raises(OSError, match="controlled audit engine close failure"):
        main(["--out", str(output), "--strict"])
    assert not output.exists()
