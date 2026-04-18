from __future__ import annotations

import copy

from scripts.productflow.productflow_support import (
    PRODUCTFLOW_BUILDER_SEAT,
    PRODUCTFLOW_EPIC_ID,
    PRODUCTFLOW_ISSUE_ID,
    PRODUCTFLOW_OUTPUT_CONTENT,
    PRODUCTFLOW_OUTPUT_PATH,
)
from scripts.proof.trusted_run_witness_support import (
    BUNDLE_SCHEMA_VERSION,
    COMPARE_SCOPE,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    build_contract_verdict,
    stable_json_digest,
)


def valid_bundle(*, session_id: str = "sess-a") -> dict[str, object]:
    run_id = f"turn-tool-run:{session_id}:PF-WRITE-1:lead_architect:0001"
    bundle = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_id": f"trusted-run-bundle:{run_id}",
        "recorded_at_utc": "2026-04-16T00:00:00Z",
        "run_id": run_id,
        "session_id": session_id,
        "compare_scope": COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "claim_tier": FALLBACK_CLAIM_TIER,
        "policy_digest": "sha256:policy",
        "policy_snapshot_ref": f"turn-tool-policy:{run_id}",
        "configuration_snapshot_ref": f"turn-tool-config:{run_id}",
        "control_bundle_ref": f"runs/{session_id}/run_summary.json#control_plane;approval:approval-1",
        "control_bundle_digest": stable_json_digest({"run_id": run_id}),
        "resolution_basis": {
            "witness": "approval.control_plane_target_ref + run_summary",
            "approval_id": "approval-1",
            "run_summary_path": f"runs/{session_id}/run_summary.json",
        },
        "productflow_slice": {
            "epic_id": PRODUCTFLOW_EPIC_ID,
            "issue_id": PRODUCTFLOW_ISSUE_ID,
            "builder_seat": PRODUCTFLOW_BUILDER_SEAT,
            "approval_reason": "approval_required_tool:write_file",
        },
        "artifact_refs": [
            {"kind": "run_summary", "path": f"runs/{session_id}/run_summary.json", "digest": "sha256:summary"},
            {"kind": "output_artifact", "path": PRODUCTFLOW_OUTPUT_PATH, "digest": "sha256:output"},
        ],
        "authority_lineage": _authority_lineage(run_id=run_id, session_id=session_id),
        "observed_effect": {
            "expected_output_artifact_path": PRODUCTFLOW_OUTPUT_PATH,
            "actual_output_artifact_path": PRODUCTFLOW_OUTPUT_PATH,
            "output_exists": True,
            "expected_normalized_content": PRODUCTFLOW_OUTPUT_CONTENT,
            "normalized_content": PRODUCTFLOW_OUTPUT_CONTENT,
            "content_sha256": "sha256:output",
            "expected_issue_status": "done",
            "issue_status": "done",
        },
    }
    bundle["contract_verdict"] = build_contract_verdict(copy.deepcopy(bundle))
    return bundle


def _authority_lineage(*, run_id: str, session_id: str) -> dict[str, object]:
    return {
        "governed_input": {
            "epic_id": PRODUCTFLOW_EPIC_ID,
            "issue_id": PRODUCTFLOW_ISSUE_ID,
            "seat": PRODUCTFLOW_BUILDER_SEAT,
            "payload_digest": "sha256:payload",
        },
        "run": {
            "run_id": run_id,
            "run_state": "completed",
            "current_attempt_id": f"{run_id}:attempt:0001",
            "current_attempt_state": "attempt_completed",
            "final_truth_record_id": f"turn-tool-final-truth:{run_id}",
            "namespace_scope": f"issue:{PRODUCTFLOW_ISSUE_ID}",
            "policy_snapshot_id": f"turn-tool-policy:{run_id}",
            "configuration_snapshot_id": f"turn-tool-config:{run_id}",
        },
        "step": {
            "step_count": 2,
            "latest_step_id": "step-2",
            "latest_output_ref": "turn-tool-result:step-2",
            "latest_resources_touched": ["tool:write_file", PRODUCTFLOW_OUTPUT_PATH, f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}"],
        },
        "approval_request": {
            "approval_id": "approval-1",
            "status": "APPROVED",
            "request_type": "tool_approval",
            "gate_mode": "approval_required",
            "reason": "approval_required_tool:write_file",
            "control_plane_target_ref": run_id,
            "payload_digest": "sha256:payload",
        },
        "operator_action": {
            "result": "approved",
            "affected_resource_refs": [f"session:{session_id}", f"issue:{PRODUCTFLOW_ISSUE_ID}", run_id],
        },
        "checkpoint": {
            "checkpoint_id": f"turn-tool-checkpoint:{run_id}:attempt:0001",
            "acceptance_outcome": "checkpoint_accepted",
            "policy_digest": "sha256:policy",
            "acceptance_dependent_reservation_refs": [f"turn-tool-reservation:{run_id}"],
            "acceptance_dependent_lease_refs": [f"turn-tool-lease:{run_id}"],
        },
        "resource": {
            "resource_id": f"namespace:issue:{PRODUCTFLOW_ISSUE_ID}",
            "namespace_scope": f"issue:{PRODUCTFLOW_ISSUE_ID}",
            "current_observed_state": f"lease_status:lease_released;namespace:issue:{PRODUCTFLOW_ISSUE_ID}",
            "provenance_ref": f"turn-tool-lease:{run_id}",
        },
        "reservation": {
            "reservation_id": f"approval-reservation:{run_id}",
            "reservation_kind": "operator_hold_reservation",
            "status": "reservation_released",
            "holder_ref": run_id,
            "target_scope_ref": f"operator-hold:session={session_id};issue={PRODUCTFLOW_ISSUE_ID};target={run_id}",
        },
        "effect_journal": {
            "effect_entry_count": 2,
            "latest_step_id": "step-2",
            "latest_authorization_basis_ref": "turn-tool-authorization:step-2",
            "latest_intended_target_ref": "tool:update_issue_status",
            "latest_observed_result_ref": "turn-tool-result:step-2",
            "latest_prior_journal_entry_id": "turn-tool-journal:step-1",
            "latest_prior_entry_digest": "sha256:prior",
            "latest_uncertainty_classification": "no_residual_uncertainty",
        },
        "final_truth": {
            "final_truth_record_id": f"turn-tool-final-truth:{run_id}",
            "result_class": "success",
            "evidence_sufficiency_classification": "evidence_sufficient",
        },
    }
