from __future__ import annotations

from pathlib import Path


def test_approval_checkpoint_docs_admit_create_directory_slice() -> None:
    """Layer: contract. Verifies approval authority names the complete bounded turn-tool family."""
    checkpoint = Path("docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md").read_text(encoding="utf-8")
    api_contract = Path("docs/API_FRONTEND_CONTRACT.md").read_text(encoding="utf-8")
    runbook = Path("docs/RUNBOOK.md").read_text(encoding="utf-8")
    authority = Path("CURRENT_AUTHORITY.md").read_text(encoding="utf-8")

    for document in (checkpoint, api_contract, runbook, authority):
        assert "`write_file`, `create_directory`, and `create_issue`" in document
    assert "four shipped bounded slices only" in api_contract
    assert "four bounded shipped slices only" in runbook
    assert "four shipped bounded approve-to-continue slices only" in authority


def test_kernel_outbound_policy_docs_name_projection_pack_gate() -> None:
    """Layer: contract. Verifies the outbound redaction gate is documented on public authority surfaces."""
    api_contract = Path("docs/API_FRONTEND_CONTRACT.md").read_text(encoding="utf-8")
    security = Path("docs/SECURITY.md").read_text(encoding="utf-8")
    authority = Path("CURRENT_AUTHORITY.md").read_text(encoding="utf-8")

    assert "`outbound_policy` with redaction settings applied before projection digesting" in api_contract
    assert "Kernel Outbound Projection Policy" in security
    assert "policy_summary.outbound_policy_gate" in authority
