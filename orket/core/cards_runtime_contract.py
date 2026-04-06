from __future__ import annotations

import json
from typing import Any

APP_EXECUTION_PROFILE = "builder_guard_app_v1"
ARTIFACT_EXECUTION_PROFILE = "builder_guard_artifact_v1"
ODR_EXECUTION_PROFILE = "odr_prebuild_builder_guard_v1"
BUILD_APP_EXECUTION_PROFILE = "build_app_v1"
WRITE_ARTIFACT_EXECUTION_PROFILE = "write_artifact_v1"
REVIEW_COMMENT_EXECUTION_PROFILE = "review_comment_v1"
CRITIQUE_COMMENT_EXECUTION_PROFILE = "critique_comment_v1"
TRUTHFUL_BLOCK_ONLY_EXECUTION_PROFILE = "truthful_block_only_v1"

DEFAULT_APP_PRIMARY_OUTPUT = "agent_output/main.py"
DEFAULT_REQUIREMENTS_PATH = "agent_output/requirements.txt"
DEFAULT_ARCHITECTURE_PATH = "agent_output/design.txt"
DEFAULT_SOURCE_ATTRIBUTION_PATH = "agent_output/source_attribution_receipt.json"
DEFAULT_RUNTIME_VERIFICATION_PATH = "agent_output/verification/runtime_verification.json"

_RUNTIME_PARAM_KEYS = (
    "cards_runtime",
    "execution_profile",
    "artifact_contract",
    "odr_enabled",
)

_PROFILE_TRAITS_BY_PROFILE = {
    APP_EXECUTION_PROFILE: {
        "intent": "build_app",
        "artifact_contract_required": True,
        "runtime_verifier_allowed": True,
    },
    BUILD_APP_EXECUTION_PROFILE: {
        "intent": "build_app",
        "artifact_contract_required": True,
        "runtime_verifier_allowed": True,
    },
    ARTIFACT_EXECUTION_PROFILE: {
        "intent": "write_artifact",
        "artifact_contract_required": True,
        "runtime_verifier_allowed": False,
    },
    WRITE_ARTIFACT_EXECUTION_PROFILE: {
        "intent": "write_artifact",
        "artifact_contract_required": True,
        "runtime_verifier_allowed": False,
    },
    REVIEW_COMMENT_EXECUTION_PROFILE: {
        "intent": "review_comment",
        "artifact_contract_required": False,
        "runtime_verifier_allowed": False,
    },
    CRITIQUE_COMMENT_EXECUTION_PROFILE: {
        "intent": "critique_comment",
        "artifact_contract_required": False,
        "runtime_verifier_allowed": False,
    },
    TRUTHFUL_BLOCK_ONLY_EXECUTION_PROFILE: {
        "intent": "truthful_block_only",
        "artifact_contract_required": False,
        "runtime_verifier_allowed": False,
    },
    ODR_EXECUTION_PROFILE: {
        "intent": "odr_prebuild_builder_guard",
        "artifact_contract_required": True,
        "runtime_verifier_allowed": False,
    },
}


def _dict_payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def apply_epic_cards_runtime_defaults(*, issue_params: Any, epic_params: Any) -> dict[str, Any]:
    issue_payload = _dict_payload(issue_params)
    epic_payload = _dict_payload(epic_params)
    if not epic_payload:
        return issue_payload

    merged = dict(issue_payload)
    epic_runtime = _dict_payload(epic_payload.get("cards_runtime"))
    issue_runtime = _dict_payload(merged.get("cards_runtime"))
    if epic_runtime or issue_runtime:
        merged["cards_runtime"] = {**epic_runtime, **issue_runtime}

    for key in _RUNTIME_PARAM_KEYS[1:]:
        if key in merged:
            continue
        if key in epic_payload:
            merged[key] = epic_payload[key]
    return merged


def resolve_cards_runtime(
    *,
    issue: Any,
    builder_seat: str = "",
    reviewer_seat: str = "",
) -> dict[str, Any]:
    issue_seat = str(getattr(issue, "seat", "") or "").strip().lower() or "coder"
    params = getattr(issue, "params", None)
    payload = _dict_payload(params)
    nested = _dict_payload(payload.get("cards_runtime"))

    requested_profile = _pick_first_token(
        nested.get("execution_profile"),
        payload.get("execution_profile"),
    )
    odr_enabled = _coerce_bool(nested.get("odr_enabled"))
    if odr_enabled is None:
        odr_enabled = _coerce_bool(payload.get("odr_enabled"))
    odr_enabled = bool(odr_enabled)

    artifact_contract = _normalize_artifact_contract(
        _dict_payload(nested.get("artifact_contract")) or payload.get("artifact_contract"),
        requested_profile=requested_profile,
    )
    profile_traits = _profile_traits_for_profile(requested_profile)
    odr_result = _dict_payload(payload.get("odr_result"))
    scenario_truth = _normalize_scenario_truth(
        _dict_payload(nested.get("scenario_truth")) or payload.get("scenario_truth"),
    )
    base_profile = _resolve_base_profile(
        requested_profile=requested_profile,
        artifact_contract=artifact_contract,
    )
    if requested_profile == ODR_EXECUTION_PROFILE:
        odr_enabled = True
    execution_profile = ODR_EXECUTION_PROFILE if odr_enabled else base_profile

    invalid_reason = ""
    if base_profile in {APP_EXECUTION_PROFILE, BUILD_APP_EXECUTION_PROFILE} and artifact_contract["kind"] != "app":
        invalid_reason = "app_profile_selected_for_non_app_artifact_contract"
    if (
        profile_traits.get("artifact_contract_required") is False
        and _artifact_contract_declares_outputs(artifact_contract)
    ):
        invalid_reason = "comment_or_block_profile_selected_for_artifact_contract"

    resolved_builder_seat = str(builder_seat or issue_seat or "coder").strip() or "coder"
    resolved_reviewer_seat = str(reviewer_seat or "integrity_guard").strip() or "integrity_guard"

    return {
        "execution_profile": execution_profile,
        "base_execution_profile": base_profile,
        "builder_seat_choice": resolved_builder_seat,
        "reviewer_seat_choice": resolved_reviewer_seat,
        "profile_traits": profile_traits,
        "odr_auditor_model": _pick_first_token(
            nested.get("odr_auditor_model"),
            payload.get("odr_auditor_model"),
        ),
        "seat_coercion": {
            "builder_issue_seat": issue_seat,
            "builder_runtime_seat": resolved_builder_seat,
            "builder_seat_coerced": bool(issue_seat and issue_seat != resolved_builder_seat.lower()),
            "reviewer_runtime_seat": resolved_reviewer_seat,
        },
        "artifact_contract": artifact_contract,
        "scenario_truth": scenario_truth,
        "odr_active": execution_profile == ODR_EXECUTION_PROFILE,
        "invalid_profile_reason": invalid_reason,
        **_normalize_odr_result(odr_result),
    }


def required_read_paths_for_seat(*, seat_name: str, issue: Any) -> list[str]:
    seat = str(seat_name or "").strip().lower()
    runtime = resolve_cards_runtime(issue=issue)
    artifact_contract = _dict_payload(runtime.get("artifact_contract"))
    review_paths = _normalize_paths(artifact_contract.get("review_read_paths"))
    issue_seat = str(getattr(issue, "seat", "") or "").strip().lower()
    reviewer_seat = str(runtime.get("reviewer_seat_choice") or "").strip().lower()

    if seat == "architect":
        return [DEFAULT_REQUIREMENTS_PATH]
    if seat == "integrity_guard":
        if issue_seat in {"code_reviewer", "reviewer"}:
            return _normalize_paths(
                DEFAULT_REQUIREMENTS_PATH,
                DEFAULT_ARCHITECTURE_PATH,
                review_paths,
                DEFAULT_RUNTIME_VERIFICATION_PATH,
            )
        return review_paths
    if seat in {"code_reviewer", "reviewer", reviewer_seat}:
        return _normalize_paths(DEFAULT_REQUIREMENTS_PATH, review_paths)
    if seat in {"coder", "developer", str(runtime.get("builder_seat_choice") or "").strip().lower()}:
        return list(artifact_contract.get("required_read_paths") or [])
    return []


def required_write_paths_for_seat(*, seat_name: str, issue: Any) -> list[str]:
    seat = str(seat_name or "").strip().lower()
    runtime = resolve_cards_runtime(issue=issue)
    artifact_contract = _dict_payload(runtime.get("artifact_contract"))
    builder_seat = str(runtime.get("builder_seat_choice") or "").strip().lower()
    if seat == "requirements_analyst":
        return [DEFAULT_REQUIREMENTS_PATH]
    if seat == "architect":
        return [DEFAULT_ARCHITECTURE_PATH]
    if seat == "evidence_reviewer":
        return [DEFAULT_SOURCE_ATTRIBUTION_PATH]
    if seat in {"code_reviewer", "reviewer", "integrity_guard"}:
        builder_seat = ""
    if seat in {"coder", "developer", builder_seat}:
        return list(artifact_contract.get("required_write_paths") or [])
    return []


def summarize_cards_runtime_issues(issue_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in issue_payloads if isinstance(row, dict)]
    if not rows:
        return {}
    profiles = sorted({str(row.get("execution_profile") or "").strip() for row in rows if str(row.get("execution_profile") or "").strip()})
    shared_profile = profiles[0] if len(profiles) == 1 else "mixed"
    odr_active = any(bool(row.get("odr_active")) for row in rows)
    summary: dict[str, Any] = {
        "issues": rows,
        "execution_profile": shared_profile,
        "odr_active": odr_active,
    }
    shared_scenario_truth = _shared_dict_value(rows=rows, key="scenario_truth")
    if shared_scenario_truth:
        summary["scenario_truth"] = shared_scenario_truth
    if len(rows) == 1:
        row = rows[0]
        for key in (
            "builder_seat_choice",
            "reviewer_seat_choice",
            "profile_traits",
            "seat_coercion",
            "artifact_contract",
            "scenario_truth",
            "odr_valid",
            "odr_pending_decisions",
            "odr_stop_reason",
            "odr_termination_reason",
            "odr_final_auditor_verdict",
            "odr_artifact_path",
        ):
            if key in row:
                summary[key] = row[key]
    return summary


def _resolve_base_profile(*, requested_profile: str, artifact_contract: dict[str, Any]) -> str:
    if requested_profile in _PROFILE_TRAITS_BY_PROFILE:
        return requested_profile
    if artifact_contract.get("kind") == "artifact":
        return ARTIFACT_EXECUTION_PROFILE
    return APP_EXECUTION_PROFILE


def _normalize_artifact_contract(value: Any, *, requested_profile: str = "") -> dict[str, Any]:
    payload = _dict_payload(value)
    profile_traits = _profile_traits_for_profile(requested_profile)
    if not payload and profile_traits.get("artifact_contract_required") is False:
        return _empty_artifact_contract()
    requested_kind = _pick_first_token(payload.get("kind"), payload.get("intent"))
    primary_output = _pick_first_token(
        payload.get("primary_output"),
        payload.get("target_path"),
        payload.get("entrypoint_path"),
    )
    write_paths = _normalize_paths(
        payload.get("required_write_paths"),
        payload.get("write_paths"),
        [primary_output] if primary_output else [],
    )
    if not write_paths:
        write_paths = [DEFAULT_APP_PRIMARY_OUTPUT]
    primary_output = primary_output or write_paths[0]

    kind = requested_kind if requested_kind in {"app", "artifact"} else _infer_contract_kind(primary_output, write_paths)
    entrypoint_path = _pick_first_token(payload.get("entrypoint_path"))
    if not entrypoint_path and kind == "app":
        entrypoint_path = DEFAULT_APP_PRIMARY_OUTPUT

    read_paths = _normalize_paths(payload.get("required_read_paths"), payload.get("read_paths"))
    review_read_paths = _normalize_paths(payload.get("review_read_paths"), write_paths)
    semantic_checks = _normalize_semantic_checks(payload.get("semantic_checks"))
    return {
        "kind": kind,
        "primary_output": primary_output,
        "required_write_paths": write_paths,
        "required_read_paths": read_paths,
        "review_read_paths": review_read_paths,
        "semantic_checks": semantic_checks,
        "entrypoint_path": entrypoint_path,
        "deployment_enabled": bool(kind == "app" and entrypoint_path == DEFAULT_APP_PRIMARY_OUTPUT),
    }


def _empty_artifact_contract() -> dict[str, Any]:
    return {
        "kind": "none",
        "primary_output": "",
        "required_write_paths": [],
        "required_read_paths": [],
        "review_read_paths": [],
        "semantic_checks": [],
        "entrypoint_path": "",
        "deployment_enabled": False,
    }


def _profile_traits_for_profile(profile: Any) -> dict[str, Any]:
    normalized = str(profile or "").strip()
    traits = _PROFILE_TRAITS_BY_PROFILE.get(normalized)
    if traits is None:
        return {
            "intent": "unspecified",
            "artifact_contract_required": True,
            "runtime_verifier_allowed": True,
        }
    return dict(traits)


def _artifact_contract_declares_outputs(artifact_contract: dict[str, Any]) -> bool:
    kind = str(artifact_contract.get("kind") or "").strip().lower()
    if kind in {"app", "artifact"}:
        return True
    for key in ("primary_output", "entrypoint_path"):
        if str(artifact_contract.get(key) or "").strip():
            return True
    for key in ("required_write_paths", "review_read_paths"):
        values = artifact_contract.get(key) or []
        if isinstance(values, list) and any(str(item or "").strip() for item in values):
            return True
    return False


def _normalize_scenario_truth(value: Any) -> dict[str, Any]:
    payload = _dict_payload(value)
    if not payload:
        return {}
    blocked_issue_policy = _dict_payload(payload.get("blocked_issue_policy"))
    normalized: dict[str, Any] = {
        "scenario_id": _pick_first_token(payload.get("scenario_id"), payload.get("id")),
        "blocked_issue_policy": {
            "allowed_issue_ids": _normalize_paths(
                blocked_issue_policy.get("allowed_issue_ids"),
                payload.get("allowed_blocked_issue_ids"),
            ),
            "blocked_implies_run_failure": bool(
                _coerce_bool(blocked_issue_policy.get("blocked_implies_run_failure"))
                if blocked_issue_policy.get("blocked_implies_run_failure") is not None
                else _coerce_bool(payload.get("blocked_implies_run_failure"))
            ),
        },
        "expected_terminal_status": _pick_first_token(payload.get("expected_terminal_status")),
        "expected_truth_classification": _pick_first_token(payload.get("expected_truth_classification")),
    }
    if not any(
        (
            normalized["scenario_id"],
            normalized["blocked_issue_policy"]["allowed_issue_ids"],
            normalized["expected_terminal_status"],
            normalized["expected_truth_classification"],
        )
    ):
        return {}
    return normalized


def normalize_scenario_truth_alignment(*, scenario_truth: Any, observed_terminal_status: str) -> dict[str, Any]:
    normalized = _normalize_scenario_truth(scenario_truth)
    if not normalized:
        return {}
    expected_terminal_status = str(normalized.get("expected_terminal_status") or "").strip().lower()
    observed = str(observed_terminal_status or "").strip().lower()
    alignment: dict[str, Any] = {
        "scenario_id": str(normalized.get("scenario_id") or "").strip(),
        "expected_terminal_status": expected_terminal_status,
        "observed_terminal_status": observed,
    }
    if expected_terminal_status:
        alignment["expected_terminal_status_match"] = expected_terminal_status == observed
    return alignment


def _infer_contract_kind(primary_output: str, write_paths: list[str]) -> str:
    if primary_output == DEFAULT_APP_PRIMARY_OUTPUT and write_paths == [DEFAULT_APP_PRIMARY_OUTPUT]:
        return "app"
    return "artifact"


def _normalize_paths(*values: Any) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            token = str(item or "").strip().replace("\\", "/")
            if not token or token in seen:
                continue
            seen.add(token)
            ordered.append(token)
    return ordered


def _normalize_semantic_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        path = _pick_first_token(item.get("path"))
        if not path:
            continue
        check = {
            "path": path.replace("\\", "/"),
            "label": _pick_first_token(item.get("label")),
            "must_contain": _normalize_paths(item.get("must_contain")),
            "must_not_contain": _normalize_paths(item.get("must_not_contain")),
        }
        if not check["must_contain"] and not check["must_not_contain"]:
            continue
        normalized.append(check)
    return normalized


def _pick_first_token(*values: Any) -> str:
    for value in values:
        token = str(value or "").strip()
        if token:
            return token
    return ""


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    raw = str(value or "").strip().lower()
    if raw in {"1", "true", "yes", "on", "enabled"}:
        return True
    if raw in {"0", "false", "no", "off", "disabled"}:
        return False
    return None


def _normalize_odr_result(value: Any) -> dict[str, Any]:
    payload = _dict_payload(value)
    normalized: dict[str, Any] = {}
    for key in (
        "odr_valid",
        "odr_pending_decisions",
        "odr_stop_reason",
        "odr_termination_reason",
        "odr_final_auditor_verdict",
        "odr_artifact_path",
        "odr_requirement",
        "odr_rounds_completed",
        "odr_accepted",
    ):
        if key not in payload:
            continue
        normalized[key] = payload[key]
    return normalized


def _shared_dict_value(*, rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    encoded: set[str] = set()
    selected: dict[str, Any] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, dict) or not value:
            continue
        encoded.add(json.dumps(value, sort_keys=True))
        selected = _dict_payload(value)
    if len(encoded) == 1:
        return selected
    return {}
