# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.security.build_tool_gate_audit import main


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
    assert isinstance(payload.get("diff_ledger"), list)
