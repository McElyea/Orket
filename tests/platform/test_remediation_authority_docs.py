"""Canonical contracts own normative text; the generated snapshot routes to them."""

from pathlib import Path

import pytest

from scripts.governance.current_authority import validate

pytestmark = pytest.mark.contract


def test_approval_checkpoint_docs_retain_the_bounded_tool_family() -> None:
    checkpoint = Path("docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md").read_text(encoding="utf-8")
    api_contract = Path("docs/API_FRONTEND_CONTRACT.md").read_text(encoding="utf-8")
    runbook = Path("docs/RUNBOOK.md").read_text(encoding="utf-8")
    for document in (checkpoint, api_contract, runbook):
        assert "`write_file`, `create_directory`, and `create_issue`" in document
    assert "four shipped bounded slices only" in api_contract
    assert "four bounded shipped slices only" in runbook
    payload, _, _ = validate(Path.cwd())
    sources = {row["source"] for row in payload["records"]}
    assert "docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md" in sources
    assert "docs/specs/TOOL_EXECUTION_GATE_V1.md" in sources


def test_kernel_outbound_policy_retains_its_canonical_contract() -> None:
    api_contract = Path("docs/API_FRONTEND_CONTRACT.md").read_text(encoding="utf-8")
    security = Path("docs/SECURITY.md").read_text(encoding="utf-8")
    assert "`outbound_policy` with redaction settings applied before projection digesting" in api_contract
    assert "Kernel Outbound Projection Policy" in security
    assert "policy_summary.outbound_policy_gate" in security
    payload, _, _ = validate(Path.cwd())
    assert any(row["source"] == "docs/SECURITY.md" for row in payload["records"])
