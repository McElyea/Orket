from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.proof.trusted_run_witness_contract import (
    BUNDLE_SCHEMA_VERSION,
    DEFAULT_BUNDLE_NAME,
    FALLBACK_CLAIM_TIER,
    OPERATOR_SURFACE,
    PROOF_RESULTS_ROOT,
    REPORT_SCHEMA_VERSION,
    TARGET_CLAIM_TIER,
    now_utc_iso,
    relative_to_repo,
    stable_json_digest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TRUSTED_REPO_COMPARE_SCOPE = "trusted_repo_config_change_v1"
CONTRACT_VERDICT_SCHEMA_VERSION = "trusted_repo_change_contract_verdict.v1"
VALIDATOR_SCHEMA_VERSION = "trusted_repo_config_validator.v1"
CONFIG_SCHEMA_VERSION = "trusted_repo_change.config.v1"
WORKFLOW_REQUEST_SCHEMA_VERSION = "trusted_repo_change.flow_request.v1"
DEFAULT_WORKSPACE_ROOT = REPO_ROOT / "workspace" / "trusted_repo_change"
CONFIG_ARTIFACT_PATH = "repo/config/trusted-change.json"
DEFAULT_LIVE_RUN_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_live_run.json"
DEFAULT_VALIDATOR_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_validator.json"
DEFAULT_CAMPAIGN_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_witness_verification.json"
DEFAULT_OFFLINE_OUTPUT = PROOF_RESULTS_ROOT / "trusted_repo_change_offline_verifier.json"
APPROVAL_REASON = "approval_required_tool:write_file"
CHANGE_ID = "TRUSTED-CHANGE-1"
RESOURCE_ID = f"fixture-path:{CONFIG_ARTIFACT_PATH}"
EXPECTED_CONFIG: dict[str, Any] = {
    "schema_version": CONFIG_SCHEMA_VERSION,
    "change_id": CHANGE_ID,
    "approved": True,
    "risk_class": "low",
    "owner": "orket-core",
    "summary": "Approved trusted repo change fixture",
}
MUST_CATCH_OUTCOMES = [
    "missing_config_artifact",
    "wrong_config_schema",
    "wrong_config_content",
    "forbidden_path_mutation",
    "missing_approval_resolution",
    "missing_validator_result",
    "validator_failed",
    "missing_effect_evidence",
    "missing_final_truth",
    "canonical_run_id_drift",
]


def expected_config_payload() -> dict[str, Any]:
    return copy.deepcopy(EXPECTED_CONFIG)


def config_schema_payload() -> dict[str, Any]:
    return {
        "schema_version": "json_schema_const_contract.v1",
        "type": "object",
        "required": list(EXPECTED_CONFIG.keys()),
        "additionalProperties": False,
        "properties": {key: {"const": value} for key, value in EXPECTED_CONFIG.items()},
    }


def validate_config_artifact(config_path: Path, *, artifact_path: str = CONFIG_ARTIFACT_PATH) -> dict[str, Any]:
    passed: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []
    missing: list[str] = []
    artifact_digest = ""
    payload: dict[str, Any] | None = None
    parse_error = ""

    if not config_path.exists():
        _fail(failed, missing, "config_artifact_exists", "missing_config_artifact")
    else:
        artifact_digest = _file_sha256(config_path)
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            loaded = None
            parse_error = f"{exc.msg}:{exc.lineno}:{exc.colno}"
        if isinstance(loaded, dict):
            payload = loaded
            _pass(passed, "config_json_object")
        else:
            _fail(failed, missing, "config_json_object", "wrong_config_schema")

    if payload is not None:
        _validate_payload(payload, passed=passed, failed=failed, missing=missing)

    schema_digest = stable_json_digest(config_schema_payload())
    report = {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "artifact_path": artifact_path,
        "artifact_digest": artifact_digest,
        "schema_digest": schema_digest,
        "validation_result": "pass" if not failed else "fail",
        "passed_checks": passed,
        "failed_checks": failed,
        "missing_evidence": _unique(missing),
        "parse_error": parse_error,
    }
    report["validator_signature_digest"] = stable_json_digest(_validator_signature_material(report))
    return report


def build_contract_verdict(bundle: dict[str, Any]) -> dict[str, Any]:
    clean = _without_diff_ledger(bundle)
    authority = _as_dict(clean.get("authority_lineage"))
    observed = _as_dict(clean.get("observed_effect"))
    validator = _as_dict(clean.get("validator_result"))
    run_id = _text(clean.get("run_id"))
    session_id = _text(clean.get("session_id"))
    failures: list[str] = []
    checks: list[dict[str, str]] = []

    def check(check_id: str, passed: bool, failure: str, detail: str = "") -> None:
        checks.append({"id": check_id, "status": "pass" if passed else "fail", "detail": detail})
        if not passed:
            _append_unique(failures, failure)

    check("schema", clean.get("schema_version") == BUNDLE_SCHEMA_VERSION, "schema_version_missing_or_unsupported")
    check("compare_scope", clean.get("compare_scope") == TRUSTED_REPO_COMPARE_SCOPE, "compare_scope_missing_or_unsupported")
    check("operator_surface", clean.get("operator_surface") == OPERATOR_SURFACE, "operator_surface_missing")
    check("policy_configuration", _has_policy_configuration(clean), "policy_or_configuration_missing")
    check("governed_input", _governed_input_ok(authority), "governed_input_missing")
    check("output_path", observed.get("actual_output_artifact_path") == CONFIG_ARTIFACT_PATH, "missing_config_artifact")
    check("output_exists", observed.get("output_exists") is True, "missing_config_artifact")
    check("artifact_digest", _artifact_digest_ok(clean, observed, validator), "missing_config_artifact")
    check("validator_present", validator.get("schema_version") == VALIDATOR_SCHEMA_VERSION, "missing_validator_result")
    check("validator_passed", validator.get("validation_result") == "pass", "validator_failed")
    _append_validator_failures(failures, validator)
    check("approval_request", _approval_request_ok(authority, run_id), "missing_approval_resolution")
    check("approval_resolution", _operator_action_ok(authority, run_id), "missing_approval_resolution")
    check("checkpoint", _checkpoint_ok(authority, run_id), "checkpoint_missing_or_drifted")
    check("resource_and_lease", _resource_and_lease_ok(authority, run_id), "resource_or_lease_evidence_missing")
    check("forbidden_mutations", not observed.get("forbidden_mutations"), "forbidden_path_mutation")
    check("effect_journal", _effect_journal_ok(authority), "missing_effect_evidence")
    check("final_truth", _final_truth_ok(authority, run_id), "missing_final_truth")
    check("run_id_lineage", _run_id_lineage_ok(authority, run_id, session_id), "canonical_run_id_drift")

    signature_material = _verdict_signature_material(checks)
    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "verdict": "pass" if not failures else "fail",
        "checks": checks,
        "failures": _unique(failures),
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
        "verdict_signature_digest": stable_json_digest(signature_material),
    }


def artifact_ref(kind: str, path: Path, workspace_root: Path, *, ref_path: str | None = None) -> dict[str, Any]:
    exists = path.exists()
    return {
        "kind": kind,
        "path": ref_path or _relative_to_workspace(path, workspace_root) if exists else "",
        "digest": _file_sha256(path) if exists else "",
        "exists": exists,
    }


def _validate_payload(
    payload: dict[str, Any],
    *,
    passed: list[dict[str, str]],
    failed: list[dict[str, str]],
    missing: list[str],
) -> None:
    expected_keys = set(EXPECTED_CONFIG.keys())
    actual_keys = set(payload.keys())
    for key in EXPECTED_CONFIG:
        if key not in payload:
            _fail(failed, missing, f"field_present:{key}", _schema_or_content_failure(key))
        elif payload.get(key) == EXPECTED_CONFIG[key]:
            _pass(passed, f"field_const:{key}")
        else:
            _fail(failed, missing, f"field_const:{key}", _schema_or_content_failure(key))
    extra = sorted(actual_keys - expected_keys)
    if extra:
        _fail(failed, missing, "additional_properties_absent", "wrong_config_content")
    else:
        _pass(passed, "additional_properties_absent")


def _schema_or_content_failure(key: str) -> str:
    return "wrong_config_schema" if key == "schema_version" else "wrong_config_content"


def _validator_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": VALIDATOR_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "artifact_path": CONFIG_ARTIFACT_PATH,
        "artifact_digest": report.get("artifact_digest"),
        "schema_digest": report.get("schema_digest"),
        "validation_result": report.get("validation_result"),
        "checks": {
            item["id"]: item["status"]
            for item in list(report.get("passed_checks") or []) + list(report.get("failed_checks") or [])
        },
        "missing_evidence": list(report.get("missing_evidence") or []),
    }


def _verdict_signature_material(checks: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_VERDICT_SCHEMA_VERSION,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "expected_artifact_path": CONFIG_ARTIFACT_PATH,
        "expected_config": expected_config_payload(),
        "checks": {str(check["id"]): str(check["status"]) for check in checks},
        "must_catch_outcomes": list(MUST_CATCH_OUTCOMES),
    }


def _append_validator_failures(failures: list[str], validator: dict[str, Any]) -> None:
    for item in validator.get("missing_evidence") or []:
        if str(item) in MUST_CATCH_OUTCOMES:
            _append_unique(failures, str(item))


def _has_policy_configuration(bundle: dict[str, Any]) -> bool:
    keys = ("policy_digest", "policy_snapshot_ref", "configuration_snapshot_ref", "control_bundle_ref")
    return all(bool(_text(bundle.get(key))) for key in keys)


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return (
        governed_input.get("schema_version") == WORKFLOW_REQUEST_SCHEMA_VERSION
        and governed_input.get("change_id") == CHANGE_ID
        and governed_input.get("artifact_path") == CONFIG_ARTIFACT_PATH
    )


def _artifact_digest_ok(bundle: dict[str, Any], observed: dict[str, Any], validator: dict[str, Any]) -> bool:
    output_ref = _artifact_ref_by_kind(bundle, "output_artifact")
    digest = _text(output_ref.get("digest"))
    return (
        bool(digest)
        and digest == _text(observed.get("artifact_digest"))
        and digest == _text(validator.get("artifact_digest"))
        and output_ref.get("path") == CONFIG_ARTIFACT_PATH
    )


def _approval_request_ok(authority: dict[str, Any], run_id: str) -> bool:
    request = _as_dict(authority.get("approval_request"))
    return (
        request.get("reason") == APPROVAL_REASON
        and request.get("control_plane_target_ref") == run_id
        and request.get("target_artifact_path") == CONFIG_ARTIFACT_PATH
    )


def _operator_action_ok(authority: dict[str, Any], run_id: str) -> bool:
    action = _as_dict(authority.get("operator_action"))
    affected_refs = [_text(item) for item in action.get("affected_resource_refs") or []]
    return _text(action.get("result")).lower() == "approved" and run_id in affected_refs


def _checkpoint_ok(authority: dict[str, Any], run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    return run_id in _text(checkpoint.get("checkpoint_id")) and checkpoint.get("acceptance_outcome") == "checkpoint_accepted"


def _resource_and_lease_ok(authority: dict[str, Any], run_id: str) -> bool:
    resource = _as_dict(authority.get("resource"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    reservation = _as_dict(authority.get("reservation"))
    lease_refs = [_text(ref) for ref in checkpoint.get("acceptance_dependent_lease_refs") or []]
    reservation_refs = [_text(ref) for ref in checkpoint.get("acceptance_dependent_reservation_refs") or []]
    reservation_text = " ".join(_text(value) for value in reservation.values())
    return (
        resource.get("resource_id") == RESOURCE_ID
        and any(run_id in ref for ref in lease_refs)
        and any(run_id in ref for ref in reservation_refs)
        and run_id in reservation_text
    )


def _effect_journal_ok(authority: dict[str, Any]) -> bool:
    journal = _as_dict(authority.get("effect_journal"))
    return (
        int(journal.get("effect_entry_count") or 0) >= 1
        and journal.get("latest_intended_target_ref") == CONFIG_ARTIFACT_PATH
        and journal.get("latest_uncertainty_classification") == "no_residual_uncertainty"
    )


def _final_truth_ok(authority: dict[str, Any], run_id: str) -> bool:
    final_truth = _as_dict(authority.get("final_truth"))
    return (
        run_id in _text(final_truth.get("final_truth_record_id"))
        and final_truth.get("result_class") == "success"
        and final_truth.get("evidence_sufficiency_classification") == "evidence_sufficient"
    )


def _run_id_lineage_ok(authority: dict[str, Any], run_id: str, session_id: str) -> bool:
    run = _as_dict(authority.get("run"))
    request = _as_dict(authority.get("approval_request"))
    final_truth = _as_dict(authority.get("final_truth"))
    return (
        bool(run_id)
        and bool(session_id)
        and session_id in run_id
        and run.get("run_id") == run_id
        and request.get("control_plane_target_ref") == run_id
        and run.get("final_truth_record_id") == final_truth.get("final_truth_record_id")
    )


def _artifact_ref_by_kind(bundle: dict[str, Any], kind: str) -> dict[str, Any]:
    for ref in bundle.get("artifact_refs") or []:
        if isinstance(ref, dict) and ref.get("kind") == kind:
            return ref
    return {}


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return relative_to_repo(path)


def _file_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _pass(passed: list[dict[str, str]], check_id: str) -> None:
    passed.append({"id": check_id, "status": "pass"})


def _fail(failed: list[dict[str, str]], missing: list[str], check_id: str, reason: str) -> None:
    failed.append({"id": check_id, "status": "fail", "reason": reason})
    _append_unique(missing, reason)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _without_diff_ledger(value: Any) -> dict[str, Any]:
    copied = copy.deepcopy(value)
    if isinstance(copied, dict):
        copied.pop("diff_ledger", None)
        return copied
    return {}


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        _append_unique(result, value)
    return result
