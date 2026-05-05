from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

PACKAGE_SCHEMA_VERSION = "trust_handoff_envelope_package.v1"
BUNDLE_SCHEMA_VERSION = "trust_handoff.bundle.v1"
SCOPE_SCHEMA_VERSION = "handoff_policy_compatibility_scope.v1"
REPORT_SCHEMA_VERSION = "trust_handoff_verifier_report.v1"
PACKAGE_DIGEST_MATERIAL_SCHEMA_VERSION = "trust_handoff_package_digest_material.v1"
COMPARE_SCOPE = "trust_handoff.packet1.single_output_policy_compat.v1"
KEY_AUTHORITY_NOTE = "envelope_digest_is_sha256_not_hmac_or_asymmetric_signature"

BUNDLE_PATH = "handoff_bundle.json"
LEDGER_EXPORT_PATH = "source_ledger_export.json"
SOURCE_WITNESS_BUNDLE_PATH = "source_outward_witness_bundle.json"
COMPATIBILITY_SCOPE_PATH = "compatibility_scope.json"
COMMITTED_OUTPUT_PATH = "artifacts/committed_output"

ADMITTED_SOURCE_WITNESS_SCOPES = frozenset({"outward_run_write_file_approved_v1"})

FAILURE_CLASSES = {
    "package_manifest_missing": "missing_evidence",
    "package_manifest_schema_invalid": "schema_invalid",
    "package_ref_outside_package": "package_boundary",
    "unexpected_package_file": "package_boundary",
    "package_digest_mismatch": "digest_mismatch",
    "bundle_missing": "missing_evidence",
    "bundle_schema_invalid": "schema_invalid",
    "envelope_digest_mismatch": "digest_mismatch",
    "ledger_export_missing": "missing_evidence",
    "ledger_export_digest_mismatch": "digest_mismatch",
    "ledger_export_partial_view": "missing_evidence",
    "ledger_event_count_mismatch": "digest_mismatch",
    "source_witness_bundle_missing": "missing_evidence",
    "source_witness_bundle_digest_mismatch": "source_witness_invalid",
    "source_witness_bundle_invalid": "source_witness_invalid",
    "approval_record_missing_or_drifted": "missing_evidence",
    "commitment_record_missing_or_drifted": "missing_evidence",
    "approval_before_commitment_ordering_violated": "ordering_violation",
    "post_approval_denial_present": "post_approval_contamination",
    "committed_output_missing": "missing_evidence",
    "committed_output_digest_mismatch": "digest_mismatch",
    "committed_output_not_ledger_anchored": "missing_evidence",
    "source_policy_digest_not_ledger_anchored": "identity_drift",
    "compatibility_scope_missing": "missing_evidence",
    "compatibility_scope_schema_invalid": "schema_invalid",
    "compatibility_scope_digest_mismatch": "digest_mismatch",
    "trust_handoff_policy_incompatible": "policy_incompatible",
    "trust_handoff_agent_not_admitted": "agent_not_admitted",
    "policy_identity_digest_mismatch": "identity_drift",
    "target_agent_id_mismatch": "identity_drift",
    "source_run_id_drift": "identity_drift",
    "handoff_acceptance_contract_incomplete": "acceptance_contract_invalid",
    "key_authority_note_missing": "missing_evidence",
}


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json_bytes(payload: bytes) -> dict[str, Any]:
    parsed = json.loads(payload.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("json_object_required")
    return parsed


def envelope_digest(bundle: dict[str, Any]) -> str:
    material = copy.deepcopy(bundle)
    material.pop("envelope_digest", None)
    return canonical_json_digest(material)


def scope_digest(scope: dict[str, Any]) -> str:
    material = copy.deepcopy(scope)
    material.pop("scope_digest", None)
    return canonical_json_digest(material)


def package_digest_material(file_bytes_by_path: dict[str, bytes]) -> dict[str, Any]:
    files = [
        {
            "path": path,
            "length_bytes": len(file_bytes_by_path[path]),
            "sha256": sha256_bytes(file_bytes_by_path[path]),
        }
        for path in sorted(file_bytes_by_path)
    ]
    return {"schema_version": PACKAGE_DIGEST_MATERIAL_SCHEMA_VERSION, "files": files}


def package_digest(file_bytes_by_path: dict[str, bytes]) -> str:
    return canonical_json_digest(package_digest_material(file_bytes_by_path))


def failure_class(reason: str | None) -> str | None:
    if reason is None:
        return None
    return FAILURE_CLASSES.get(reason, "missing_evidence")


def stable_invariant_signature(checks: list[dict[str, Any]], reason: str | None) -> str:
    material = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "compare_scope": COMPARE_SCOPE,
        "checks": [
            {
                "check_id": str(item.get("check_id") or ""),
                "passed": bool(item.get("passed")),
            }
            for item in checks
        ],
        "rejection_reason": reason,
    }
    return canonical_json_digest(material)


def validate_report_conformance(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("key_authority_note") != KEY_AUTHORITY_NOTE:
        return {
            "result": "rejected",
            "rejection_reason": "key_authority_note_missing",
            "rejection_class": failure_class("key_authority_note_missing"),
        }
    return {"result": "accepted", "rejection_reason": None, "rejection_class": None}
