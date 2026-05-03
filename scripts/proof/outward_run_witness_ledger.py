from __future__ import annotations

import hashlib
from typing import Any

from orket.core.domain.outward_ledger import verify_ledger_export

from scripts.proof.outward_run_witness_contract import DEFAULT_LEDGER_EXPORT_PATH
from scripts.proof.outward_run_witness_package import OutwardRunWitnessPackage


def verify_package_ledger(package: OutwardRunWitnessPackage, *, require_full: bool = True) -> dict[str, Any]:
    ledger_evidence = package.bundle.get("ledger_evidence")
    if not isinstance(ledger_evidence, dict):
        return _failure("ledger_chain_broken")

    ledger_path = str(package.manifest.get("ledger_export_path") or DEFAULT_LEDGER_EXPORT_PATH)
    actual_digest = package.file_digests.get(ledger_path)
    if not actual_digest:
        return _failure("ledger_export_missing")
    expected_digest = str(ledger_evidence.get("ledger_export_digest") or "").strip()
    if not expected_digest:
        return _failure("missing_authority_digest")
    if _clean_digest(expected_digest) != actual_digest:
        return _failure("ledger_export_digest_mismatch")

    export_scope = str(package.ledger_export.get("export_scope") or "")
    if require_full and export_scope != "all":
        return _failure("full_ledger_export_required")
    if _payload_bytes_missing(package.ledger_export):
        return _failure("ledger_payload_bytes_missing")

    verification = verify_ledger_export(package.ledger_export)
    if verification.get("result") == "invalid":
        return _failure(_ledger_failure_code(verification))
    expected_hash = str(ledger_evidence.get("ledger_hash") or "").strip()
    if not expected_hash:
        return _failure("missing_authority_digest")
    if expected_hash != str(verification.get("ledger_hash") or ""):
        return _failure("ledger_chain_hash_mismatch")
    if int(ledger_evidence.get("event_count") or 0) != int(verification.get("event_count") or 0):
        return _failure("ledger_chain_hash_mismatch")
    if str(ledger_evidence.get("export_scope") or "") != export_scope:
        return _failure("full_ledger_export_required")

    return {
        "result": "pass",
        "failure_code": None,
        "ledger_verification": verification,
    }


def verify_committed_artifact(package: OutwardRunWitnessPackage) -> dict[str, Any]:
    artifact = package.artifacts.get("committed_output")
    if artifact is None:
        return _failure("committed_artifact_missing")
    ref = _committed_artifact_ref(package.bundle)
    if not ref:
        return _failure("committed_artifact_missing")
    expected_digest = str(ref.get("digest") or "").strip()
    if not expected_digest:
        return _failure("missing_authority_digest")
    actual_digest = hashlib.sha256(artifact).hexdigest()
    if _clean_digest(expected_digest) != actual_digest:
        return _failure("artifact_digest_mismatch")
    return {
        "result": "pass",
        "failure_code": None,
        "artifact_role": "committed_output",
        "artifact_digest": actual_digest,
    }


def _committed_artifact_ref(bundle: dict[str, Any]) -> dict[str, Any] | None:
    for ref in bundle.get("artifact_refs") or []:
        if not isinstance(ref, dict):
            continue
        role = str(ref.get("artifact_role") or ref.get("role") or "")
        if role == "committed_output":
            return ref
    return None


def _payload_bytes_missing(ledger_export: dict[str, Any]) -> bool:
    events = ledger_export.get("events")
    if not isinstance(events, list):
        return True
    return any(isinstance(event, dict) and "payload" not in event for event in events)


def _ledger_failure_code(verification: dict[str, Any]) -> str:
    errors = [str(item) for item in verification.get("errors") or []]
    if any("ledger_hash" in error or "final chain_hash" in error for error in errors):
        return "ledger_chain_hash_mismatch"
    return "ledger_chain_broken"


def _clean_digest(value: str) -> str:
    return value.removeprefix("sha256:")


def _failure(code: str) -> dict[str, Any]:
    return {"result": "fail", "failure_code": code}
