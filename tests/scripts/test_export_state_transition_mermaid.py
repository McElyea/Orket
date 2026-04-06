# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.export_state_transition_mermaid import (
    build_state_transition_mermaid,
    export_state_transition_mermaid,
    main,
)


# Layer: contract
def test_build_state_transition_mermaid_contains_domain_subgraphs() -> None:
    mermaid = build_state_transition_mermaid()
    assert mermaid.startswith("flowchart LR\n")
    assert 'subgraph session["session"]' in mermaid
    assert "session__running --> session__done" in mermaid


# Layer: integration
def test_export_state_transition_mermaid_writes_mermaid_and_json(tmp_path: Path) -> None:
    out_mermaid = tmp_path / "state.mmd"
    out_json = tmp_path / "state.json"
    payload = export_state_transition_mermaid(out_mermaid=out_mermaid, out_json=out_json)
    assert payload["ok"] is True
    assert out_mermaid.exists()
    written = json.loads(out_json.read_text(encoding="utf-8"))
    assert written["schema_version"] == "1.0"
    assert "diff_ledger" in written


# Layer: integration
def test_main_returns_success_and_writes_outputs(tmp_path: Path) -> None:
    out_mermaid = tmp_path / "out" / "state.mmd"
    out_json = tmp_path / "out" / "state.json"
    exit_code = main(["--out-mermaid", str(out_mermaid), "--out-json", str(out_json)])
    assert exit_code == 0
    assert out_mermaid.exists()
    assert out_json.exists()
