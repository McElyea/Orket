"""Explicit fixture recovery inputs; the application still validates retained authority."""
from __future__ import annotations


def recovery_request(owner, request_id="recovery-1", *, operator_ref="operator:fixture",
                     reason_ref="evidence:interrupted-fixture-export"):
    return {"schema_version": "epic_export_recovery_request.v1", "session_id": owner.session_id,
            "request_id": request_id, "expected_owner_id": owner.owner_id,
            "expected_fencing_generation": owner.fencing_generation, "expected_claim_digest": owner.claim_ref()["digest"],
            "expected_intent_digest": owner.intent_digest, "operator_ref": operator_ref,
            "reason_ref": reason_ref, "resolution": "retry_exact_commit"}
