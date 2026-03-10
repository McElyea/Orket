from __future__ import annotations

import pytest

from orket.runtime.runtime_boundary_audit_checklist import (
    runtime_boundary_audit_checklist_snapshot,
    validate_runtime_boundary_audit_checklist,
)


# Layer: unit
def test_runtime_boundary_audit_checklist_snapshot_contains_expected_boundaries() -> None:
    payload = runtime_boundary_audit_checklist_snapshot()
    assert payload["schema_version"] == "1.0"
    boundary_ids = {row["boundary_id"] for row in payload["boundaries"]}
    assert "BND-API-ENTRY" in boundary_ids
    assert "BND-WEBHOOK-GITEA" in boundary_ids


# Layer: contract
def test_validate_runtime_boundary_audit_checklist_accepts_current_snapshot() -> None:
    boundary_ids = validate_runtime_boundary_audit_checklist()
    assert "BND-BACKGROUND-LIVE-LOOP" in boundary_ids


# Layer: contract
def test_validate_runtime_boundary_audit_checklist_rejects_invalid_exception_policy() -> None:
    payload = runtime_boundary_audit_checklist_snapshot()
    payload["boundaries"][0]["exception_policy"] = "retry_forever"
    with pytest.raises(ValueError, match="E_RUNTIME_BOUNDARY_EXCEPTION_POLICY_INVALID:BND-API-ENTRY"):
        _ = validate_runtime_boundary_audit_checklist(payload)
