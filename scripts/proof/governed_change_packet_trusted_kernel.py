from __future__ import annotations

import copy
from collections import deque
from typing import Any

from scripts.proof.governed_change_packet_contract import (
    GOVERNED_CHANGE_PACKET_KERNEL_CONFORMANCE_SCHEMA_VERSION,
    GOVERNED_CHANGE_PACKET_KERNEL_MODEL_SCHEMA_VERSION,
)
from scripts.proof.trusted_repo_change_contract import (
    CONFIG_ARTIFACT_PATH,
    OPERATOR_SURFACE,
    TRUSTED_REPO_COMPARE_SCOPE,
    now_utc_iso,
    stable_json_digest,
)

_ACTION_ORDER = (
    "bind_governed_input",
    "bind_policy_configuration",
    "bind_approval",
    "accept_checkpoint",
    "activate_lease",
    "invalidate_lease",
    "publish_effect",
    "publish_validator_success",
    "publish_final_truth_success",
    "publish_final_truth_failure",
    "verify_packet",
)


def build_governed_change_packet_trusted_kernel_report() -> dict[str, Any]:
    initial = _initial_state()
    queue: deque[tuple[dict[str, Any], list[str]]] = deque([(initial, [])])
    seen = {_state_key(initial)}
    reachable = 0
    rejected_examples: list[dict[str, Any]] = []
    verifier_checks = 0
    invariant_failures: list[dict[str, Any]] = []

    while queue:
        state, trace = queue.popleft()
        reachable += 1
        failures = _invariant_failures(state)
        if failures:
            invariant_failures.append({"trace": trace, "failures": failures, "state": copy.deepcopy(state)})
        for action in _ACTION_ORDER:
            next_state, rejection_reason = _apply_action(state, action)
            if rejection_reason:
                if len(rejected_examples) < 12:
                    rejected_examples.append(
                        {
                            "action": action,
                            "trace": trace,
                            "reason": rejection_reason,
                        }
                    )
                continue
            if action == "verify_packet":
                verifier_checks += 1
                if not _verification_path_is_inspection_only(state, next_state):
                    invariant_failures.append(
                        {
                            "trace": trace + [action],
                            "failures": ["verifier_path_not_inspection_only"],
                            "state": copy.deepcopy(next_state),
                        }
                    )
            key = _state_key(next_state)
            if key not in seen:
                seen.add(key)
                queue.append((next_state, trace + [action]))

    result = "success" if not invariant_failures else "failure"
    checks = [
        _check("kernel_no_effect_without_accepted_authority", not _any_failure(invariant_failures, "effect_without_accepted_authority")),
        _check(
            "kernel_no_success_final_truth_without_validator_and_effect",
            not _any_failure(invariant_failures, "success_final_truth_without_validator_and_effect"),
        ),
        _check("kernel_no_contradictory_final_truth", not _any_failure(invariant_failures, "contradictory_final_truth")),
        _check("kernel_no_lease_reuse_after_invalidation", not _any_failure(invariant_failures, "lease_reused_after_invalidation")),
        _check("kernel_verifier_inspection_only", not _any_failure(invariant_failures, "verifier_path_not_inspection_only")),
    ]
    report = {
        "schema_version": GOVERNED_CHANGE_PACKET_KERNEL_MODEL_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "proof_kind": "structural",
        "observed_path": "primary",
        "observed_result": result,
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "model_surface": "bounded_python_state_machine",
        "reachable_state_count": reachable,
        "rejected_transition_examples": rejected_examples,
        "verification_transition_count": verifier_checks,
        "checks": checks,
        "invariant_failures": invariant_failures,
        "limitations": [
            "bounded state exploration over the admitted governed repo change packet kernel only",
            "does not prove the whole Python runtime or provider behavior",
        ],
    }
    report["model_signature_digest"] = stable_json_digest(_model_signature_material(report))
    return report


def evaluate_governed_change_packet_kernel_conformance(
    *,
    bundle: dict[str, Any],
    live_report: dict[str, Any],
    campaign_report: dict[str, Any],
    offline_report: dict[str, Any],
    model_report: dict[str, Any],
    artifact_refs: dict[str, str],
) -> dict[str, Any]:
    authority = _as_dict(bundle.get("authority_lineage"))
    run = _as_dict(authority.get("run"))
    checkpoint = _as_dict(authority.get("checkpoint"))
    validator = _as_dict(bundle.get("validator_result"))
    observed = _as_dict(bundle.get("observed_effect"))
    final_truth = _as_dict(authority.get("final_truth"))
    policy_ok = bool(bundle.get("policy_digest")) and bool(bundle.get("policy_snapshot_ref")) and bool(bundle.get("configuration_snapshot_ref"))
    obligations = [
        _obligation("GCP-KER-001", "governed_input_identity", _governed_input_ok(authority), artifact_refs.get("flow_request", "")),
        _obligation("GCP-KER-002", "resolved_policy_configuration_identity", policy_ok, artifact_refs.get("run_authority", "")),
        _obligation("GCP-KER-003", "approval_binding", _approval_binding_ok(authority, live_report), artifact_refs.get("run_authority", "")),
        _obligation(
            "GCP-KER-004",
            "reservation_and_lease_authority",
            _reservation_lease_ok(authority, run_id=str(bundle.get("run_id") or "")),
            artifact_refs.get("run_authority", ""),
        ),
        _obligation(
            "GCP-KER-005",
            "checkpoint_acceptance_before_effect",
            checkpoint.get("acceptance_outcome") == "checkpoint_accepted" and int(_as_dict(authority.get("effect_journal")).get("effect_entry_count") or 0) >= 1,
            artifact_refs.get("run_authority", ""),
        ),
        _obligation(
            "GCP-KER-006",
            "effect_publication_and_lineage",
            observed.get("actual_output_artifact_path") == CONFIG_ARTIFACT_PATH and observed.get("output_exists") is True,
            artifact_refs.get("witness_bundle", ""),
        ),
        _obligation(
            "GCP-KER-007",
            "deterministic_validator_result",
            validator.get("validation_result") == "pass" and bool(validator.get("validator_signature_digest")),
            artifact_refs.get("validator_report", ""),
        ),
        _obligation(
            "GCP-KER-008",
            "final_truth_publication_and_uniqueness",
            run.get("final_truth_record_id") == final_truth.get("final_truth_record_id")
            and final_truth.get("result_class") == "success",
            artifact_refs.get("run_authority", ""),
        ),
        _obligation(
            "GCP-KER-009",
            "witness_bundle_completeness_for_bounded_claim",
            campaign_report.get("observed_result") == "success"
            and offline_report.get("claim_tier") == "verdict_deterministic"
            and bundle.get("compare_scope") == TRUSTED_REPO_COMPARE_SCOPE,
            artifact_refs.get("campaign_report", ""),
        ),
        _obligation(
            "GCP-KER-010",
            "verifier_non_interference",
            model_report.get("observed_result") == "success"
            and live_report.get("witness_report", {}).get("side_effect_free_verification") is True
            and offline_report.get("side_effect_free_verification") is True,
            artifact_refs.get("trusted_kernel_model_check", ""),
        ),
    ]
    result = "pass" if all(item["status"] == "pass" for item in obligations) else "fail"
    report = {
        "schema_version": GOVERNED_CHANGE_PACKET_KERNEL_CONFORMANCE_SCHEMA_VERSION,
        "recorded_at_utc": now_utc_iso(),
        "compare_scope": TRUSTED_REPO_COMPARE_SCOPE,
        "operator_surface": OPERATOR_SURFACE,
        "result": result,
        "obligations": obligations,
        "missing_or_failed_obligations": [item["name"] for item in obligations if item["status"] != "pass"],
    }
    report["conformance_signature_digest"] = stable_json_digest(_conformance_signature_material(report))
    return report


def _initial_state() -> dict[str, Any]:
    return {
        "governed_input_bound": False,
        "policy_configuration_bound": False,
        "approval_bound": False,
        "checkpoint_accepted": False,
        "lease_active": False,
        "lease_invalidated": False,
        "effect_published": False,
        "effect_published_under_authority": False,
        "effect_after_invalidation": False,
        "validator_passed": False,
        "final_truth": "",
        "verification_observed": False,
    }


def _apply_action(state: dict[str, Any], action: str) -> tuple[dict[str, Any], str]:
    next_state = copy.deepcopy(state)
    if action == "bind_governed_input":
        return _set_once(next_state, "governed_input_bound")
    if action == "bind_policy_configuration":
        if not state["governed_input_bound"]:
            return state, "governed_input_not_bound"
        return _set_once(next_state, "policy_configuration_bound")
    if action == "bind_approval":
        if not state["policy_configuration_bound"]:
            return state, "policy_configuration_not_bound"
        return _set_once(next_state, "approval_bound")
    if action == "accept_checkpoint":
        if not state["approval_bound"]:
            return state, "approval_not_bound"
        return _set_once(next_state, "checkpoint_accepted")
    if action == "activate_lease":
        if not state["checkpoint_accepted"]:
            return state, "checkpoint_not_accepted"
        if state["lease_invalidated"]:
            return state, "lease_reuse_after_invalidation_blocked"
        return _set_once(next_state, "lease_active")
    if action == "invalidate_lease":
        if not state["lease_active"]:
            return state, "lease_not_active"
        next_state["lease_active"] = False
        next_state["lease_invalidated"] = True
        return next_state, ""
    if action == "publish_effect":
        if not (state["approval_bound"] and state["checkpoint_accepted"] and state["lease_active"]):
            return state, "effect_requires_authority"
        if state["lease_invalidated"]:
            next_state["effect_after_invalidation"] = True
        next_state["effect_published_under_authority"] = True
        return _set_once(next_state, "effect_published")
    if action == "publish_validator_success":
        if not state["effect_published"]:
            return state, "validator_requires_effect"
        return _set_once(next_state, "validator_passed")
    if action == "publish_final_truth_success":
        if state["final_truth"]:
            return state, "final_truth_already_published"
        if not (state["effect_published"] and state["validator_passed"]):
            return state, "success_final_truth_requires_effect_and_validator"
        next_state["final_truth"] = "success"
        return next_state, ""
    if action == "publish_final_truth_failure":
        if state["final_truth"]:
            return state, "final_truth_already_published"
        next_state["final_truth"] = "failure"
        return next_state, ""
    if action == "verify_packet":
        next_state["verification_observed"] = True
        return next_state, ""
    return state, "unsupported_action"


def _set_once(state: dict[str, Any], key: str) -> tuple[dict[str, Any], str]:
    if state[key]:
        return state, f"{key}_already_set"
    state[key] = True
    return state, ""


def _invariant_failures(state: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if state["effect_published"] and not state["effect_published_under_authority"]:
        failures.append("effect_without_accepted_authority")
    if state["final_truth"] == "success" and not (state["effect_published"] and state["validator_passed"]):
        failures.append("success_final_truth_without_validator_and_effect")
    if state["final_truth"] not in {"", "success", "failure"}:
        failures.append("contradictory_final_truth")
    if state["effect_after_invalidation"]:
        failures.append("lease_reused_after_invalidation")
    return failures


def _verification_path_is_inspection_only(before: dict[str, Any], after: dict[str, Any]) -> bool:
    changed_keys = {key for key, value in after.items() if before.get(key) != value}
    return changed_keys <= {"verification_observed"}


def _model_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GOVERNED_CHANGE_PACKET_KERNEL_MODEL_SCHEMA_VERSION,
        "observed_result": report.get("observed_result"),
        "checks": {item["id"]: item["status"] for item in report.get("checks") or []},
        "reachable_state_count": report.get("reachable_state_count"),
    }


def _conformance_signature_material(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GOVERNED_CHANGE_PACKET_KERNEL_CONFORMANCE_SCHEMA_VERSION,
        "result": report.get("result"),
        "obligations": {item["obligation_id"]: item["status"] for item in report.get("obligations") or []},
    }


def _state_key(state: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(state[key] for key in sorted(state))


def _check(check_id: str, passed: bool) -> dict[str, str]:
    return {"id": check_id, "status": "pass" if passed else "fail"}


def _any_failure(failures: list[dict[str, Any]], target: str) -> bool:
    return any(target in item.get("failures", []) for item in failures)


def _obligation(obligation_id: str, name: str, passed: bool, source_ref: str) -> dict[str, str]:
    return {
        "obligation_id": obligation_id,
        "name": name,
        "status": "pass" if passed else "fail",
        "source_ref": source_ref,
    }


def _governed_input_ok(authority: dict[str, Any]) -> bool:
    governed_input = _as_dict(authority.get("governed_input"))
    return governed_input.get("change_id") == "TRUSTED-CHANGE-1" and governed_input.get("artifact_path") == CONFIG_ARTIFACT_PATH


def _approval_binding_ok(authority: dict[str, Any], live_report: dict[str, Any]) -> bool:
    request = _as_dict(authority.get("approval_request"))
    action = _as_dict(authority.get("operator_action"))
    run_id = str(live_report.get("run_id") or "")
    return (
        request.get("target_artifact_path") == CONFIG_ARTIFACT_PATH
        and request.get("control_plane_target_ref") == run_id
        and str(action.get("result") or "").lower() == "approved"
    )


def _reservation_lease_ok(authority: dict[str, Any], *, run_id: str) -> bool:
    checkpoint = _as_dict(authority.get("checkpoint"))
    reservation_refs = list(checkpoint.get("acceptance_dependent_reservation_refs") or [])
    lease_refs = list(checkpoint.get("acceptance_dependent_lease_refs") or [])
    return any(run_id in str(item) for item in reservation_refs + lease_refs)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
