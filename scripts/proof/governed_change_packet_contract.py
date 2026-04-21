from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.proof.offline_trusted_run_verifier import TARGET_CLAIM_TIER
from scripts.proof.trusted_repo_change_contract import (
    CONFIG_ARTIFACT_PATH,
    DEFAULT_OFFLINE_OUTPUT,
    DEFAULT_WORKSPACE_ROOT,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    TRUSTED_REPO_COMPARE_SCOPE,
    now_utc_iso,
    relative_to_repo,
    stable_json_digest,
)

GOVERNED_CHANGE_PACKET_SCHEMA_VERSION = "governed_change_packet.v1"
GOVERNED_CHANGE_PACKET_FAMILY = "governed_repo_change_packet_v1"
GOVERNED_CHANGE_PACKET_VERIFIER_SCHEMA_VERSION = "governed_change_packet_standalone_verifier.v1"
GOVERNED_CHANGE_PACKET_KERNEL_MODEL_SCHEMA_VERSION = "governed_change_packet_trusted_kernel_model.v1"
GOVERNED_CHANGE_PACKET_KERNEL_CONFORMANCE_SCHEMA_VERSION = "governed_change_packet_trusted_kernel_conformance.v1"
DEFAULT_GOVERNED_CHANGE_PACKET_OUTPUT = PROOF_RESULTS_ROOT / "governed_repo_change_packet.json"
DEFAULT_GOVERNED_CHANGE_PACKET_VERIFIER_OUTPUT = PROOF_RESULTS_ROOT / "governed_repo_change_packet_verifier.json"
DEFAULT_GOVERNED_CHANGE_PACKET_KERNEL_MODEL_OUTPUT = PROOF_RESULTS_ROOT / "governed_change_packet_trusted_kernel_model.json"
DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_WORKSPACE_ROOT = (
    DEFAULT_WORKSPACE_ROOT.parent / "trusted_repo_change_packet_benchmark"
)
DEFAULT_GOVERNED_CHANGE_PACKET_BENCHMARK_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "staging"
    / "General"
    / "governed_repo_change_packet_adversarial_benchmark_2026-04-19.json"
)
DEFAULT_TRUSTED_REPO_DENIAL_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_denial.json"
DEFAULT_TRUSTED_REPO_VALIDATOR_FAILURE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_validator_failure.json"
REQUIRED_PACKET_ARTIFACT_ROLES = (
    "approved_live_proof",
    "flow_request",
    "run_authority",
    "validator_report",
    "witness_bundle",
    "campaign_report",
    "offline_verifier_report",
    "trusted_kernel_model_check",
)
PRIMARY_AUTHORITY_CLASSIFICATIONS = {"primary_authority", "authority_bearing"}
NEGATIVE_PROOF_CLASSIFICATION = "negative_proof"
ENTRY_PROJECTION_CLASSIFICATION = "entry_projection"


def load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required:{relative_to_repo(path)}")
    return payload


def resolve_repo_path(ref: str | Path) -> Path:
    path = Path(ref)
    return path if path.is_absolute() else (Path(__file__).resolve().parents[2] / path).resolve()


def json_file_digest(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return stable_json_digest(_artifact_digest_payload(payload))


def without_diff_ledger(value: dict[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(value)
    payload.pop("diff_ledger", None)
    return payload


def _artifact_digest_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _artifact_digest_payload(child)
            for key, child in value.items()
            if key not in {"diff_ledger", "recorded_at_utc", "verified_at_utc"}
        }
    if isinstance(value, list):
        return [_artifact_digest_payload(item) for item in value]
    return value


def packet_id(session_id: str) -> str:
    return f"governed-change-packet:{TRUSTED_REPO_COMPARE_SCOPE}:{session_id}"


def packet_entry_disclaimer() -> str:
    return (
        "Primary operator entry artifact only. Claim-bearing checks resolve to "
        "the underlying authority artifacts and verifier outputs rather than to "
        "packet projections alone."
    )


def default_limitations() -> list[str]:
    return [
        "trusted_repo_config_change_v1 only",
        "fixture-bounded local repo config change only",
        "replay determinism not yet proven",
        "text determinism not yet proven",
        "does not claim mathematical proof of the whole runtime",
    ]


def artifact_manifest_entry(
    *,
    role: str,
    path: Path,
    classification: str,
    required: bool,
    title: str,
    schema_version: str = "",
    summary: str = "",
) -> dict[str, Any]:
    exists = path.exists()
    return {
        "role": role,
        "title": title,
        "classification": classification,
        "required": required,
        "path": relative_to_repo(path) if exists else relative_to_repo(path),
        "exists": exists,
        "digest": json_file_digest(path) if exists else "",
        "schema_version": schema_version,
        "summary": summary,
    }


def packet_signature_material(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GOVERNED_CHANGE_PACKET_SIGNATURE_SCHEMA_VERSION,
        "packet_id": packet.get("packet_id"),
        "packet_family": packet.get("packet_family"),
        "compare_scope": packet.get("compare_scope"),
        "operator_surface": packet.get("operator_surface"),
        "observed_result": packet.get("observed_result"),
        "claim_summary": {
            "requested_claim_tier": packet.get("claim_summary", {}).get("requested_claim_tier"),
            "current_truthful_claim_ceiling": packet.get("claim_summary", {}).get("current_truthful_claim_ceiling"),
        },
        "artifact_manifest": {
            item["role"]: {
                "classification": item["classification"],
                "path": item["path"],
                "digest": item["digest"],
                "required": item["required"],
            }
            for item in packet.get("artifact_manifest") or []
            if isinstance(item, dict)
        },
        "trusted_kernel": {
            "model_result": packet.get("trusted_kernel", {}).get("model_check", {}).get("observed_result"),
            "conformance_result": packet.get("trusted_kernel", {}).get("conformance", {}).get("result"),
            "obligations": {
                item["obligation_id"]: item["status"]
                for item in packet.get("trusted_kernel", {}).get("conformance", {}).get("obligations") or []
                if isinstance(item, dict)
            },
        },
    }


def packet_verifier_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GOVERNED_CHANGE_PACKET_SIGNATURE_SCHEMA_VERSION,
        "packet_id": report.get("packet_id"),
        "packet_verdict": report.get("packet_verdict"),
        "observed_result": report.get("observed_result"),
        "compare_scope": report.get("compare_scope"),
        "operator_surface": report.get("operator_surface"),
        "selected_claim_tier": report.get("claim_tier"),
        "check_statuses": {item["id"]: item["status"] for item in report.get("checks") or [] if isinstance(item, dict)},
        "required_role_statuses": {
            item["role"]: item["status"]
            for item in report.get("required_role_diagnostics") or []
            if isinstance(item, dict)
        },
        "authority_ref_statuses": {
            item["role"]: item["status"]
            for item in report.get("authority_ref_diagnostics") or []
            if isinstance(item, dict)
        },
        "claim_diagnostics": {
            "requested_claim_tier": report.get("claim_diagnostics", {}).get("requested_claim_tier"),
            "selected_claim_tier": report.get("claim_diagnostics", {}).get("selected_claim_tier"),
            "requested_claim_allowed": report.get("claim_diagnostics", {}).get("requested_claim_allowed"),
            "downgrade_or_rejection_reasons": list(
                report.get("claim_diagnostics", {}).get("downgrade_or_rejection_reasons") or []
            ),
        },
        "missing_evidence": list(report.get("missing_evidence") or []),
        "contradictions": list(report.get("contradictions") or []),
    }


def packet_summary(
    *,
    live_report: dict[str, Any],
    offline_report: dict[str, Any],
) -> dict[str, Any]:
    validator_result = live_report.get("validator_result") or {}
    return {
        "workflow_question": (
            "Can Orket prove one governed repo config change strongly enough that "
            "an outside operator can inspect the packet, run a standalone verifier, "
            "and reject overclaim without trusting Orket first?"
        ),
        "requested_change_id": "TRUSTED-CHANGE-1",
        "target_artifact_path": CONFIG_ARTIFACT_PATH,
        "run_id": str(live_report.get("run_id") or ""),
        "session_id": str(live_report.get("session_id") or ""),
        "workflow_result": str(live_report.get("workflow_result") or ""),
        "artifact_changed": live_report.get("artifact_changed") is True,
        "artifact_digest_before": str(live_report.get("artifact_digest_before") or ""),
        "artifact_digest_after": str(live_report.get("artifact_digest_after") or ""),
        "validator_result": str(validator_result.get("validation_result") or ""),
        "current_truthful_claim_ceiling": str(offline_report.get("claim_tier") or ""),
    }


def packet_claim_summary(offline_report: dict[str, Any]) -> dict[str, Any]:
    claim_basis = offline_report.get("claim_ladder_basis") if isinstance(offline_report.get("claim_ladder_basis"), dict) else {}
    return {
        "requested_claim_tier": str((claim_basis.get("requested_claims") or [TARGET_CLAIM_TIER])[0]),
        "current_truthful_claim_ceiling": str(offline_report.get("claim_tier") or ""),
        "allowed_claims": list(offline_report.get("allowed_claims") or []),
        "forbidden_claims": copy.deepcopy(list(offline_report.get("forbidden_claims") or [])),
        "claim_status": str(offline_report.get("claim_status") or ""),
        "replay_determinism_proven": False,
        "text_determinism_proven": False,
        "fixture_bounded": True,
    }


def stable_signature_digest(payload: dict[str, Any]) -> str:
    return stable_json_digest(payload)


GOVERNED_CHANGE_PACKET_SIGNATURE_SCHEMA_VERSION = "governed_change_packet.signature_material.v1"
