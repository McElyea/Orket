from __future__ import annotations

from typing import Any, Dict, List

APP_EXECUTION_PROFILE = "builder_guard_app_v1"
ARTIFACT_EXECUTION_PROFILE = "builder_guard_artifact_v1"
ODR_EXECUTION_PROFILE = "odr_prebuild_builder_guard_v1"

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


def apply_epic_cards_runtime_defaults(*, issue_params: Any, epic_params: Any) -> Dict[str, Any]:
    issue_payload = dict(issue_params or {}) if isinstance(issue_params, dict) else {}
    epic_payload = dict(epic_params or {}) if isinstance(epic_params, dict) else {}
    if not epic_payload:
        return issue_payload

    merged = dict(issue_payload)
    epic_runtime = epic_payload.get("cards_runtime") if isinstance(epic_payload.get("cards_runtime"), dict) else {}
    issue_runtime = merged.get("cards_runtime") if isinstance(merged.get("cards_runtime"), dict) else {}
    if epic_runtime or issue_runtime:
        merged["cards_runtime"] = {**dict(epic_runtime), **dict(issue_runtime)}

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
) -> Dict[str, Any]:
    issue_seat = str(getattr(issue, "seat", "") or "").strip().lower() or "coder"
    params = getattr(issue, "params", None)
    payload = dict(params or {}) if isinstance(params, dict) else {}
    nested = payload.get("cards_runtime") if isinstance(payload.get("cards_runtime"), dict) else {}

    requested_profile = _pick_first_token(
        nested.get("execution_profile"),
        payload.get("execution_profile"),
    )
    odr_enabled = _coerce_bool(nested.get("odr_enabled"))
    if odr_enabled is None:
        odr_enabled = _coerce_bool(payload.get("odr_enabled"))
    odr_enabled = bool(odr_enabled)

    artifact_contract = _normalize_artifact_contract(
        nested.get("artifact_contract")
        if isinstance(nested.get("artifact_contract"), dict)
        else payload.get("artifact_contract"),
    )
    odr_result = payload.get("odr_result") if isinstance(payload.get("odr_result"), dict) else {}
    base_profile = _resolve_base_profile(
        requested_profile=requested_profile,
        artifact_contract=artifact_contract,
    )
    if requested_profile == ODR_EXECUTION_PROFILE:
        odr_enabled = True
    execution_profile = ODR_EXECUTION_PROFILE if odr_enabled else base_profile

    invalid_reason = ""
    if base_profile == APP_EXECUTION_PROFILE and artifact_contract["kind"] != "app":
        invalid_reason = "app_profile_selected_for_non_app_artifact_contract"

    resolved_builder_seat = str(builder_seat or issue_seat or "coder").strip() or "coder"
    resolved_reviewer_seat = str(reviewer_seat or "integrity_guard").strip() or "integrity_guard"

    return {
        "execution_profile": execution_profile,
        "base_execution_profile": base_profile,
        "builder_seat_choice": resolved_builder_seat,
        "reviewer_seat_choice": resolved_reviewer_seat,
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
        "odr_active": execution_profile == ODR_EXECUTION_PROFILE,
        "invalid_profile_reason": invalid_reason,
        **_normalize_odr_result(odr_result),
    }


def required_read_paths_for_seat(*, seat_name: str, issue: Any) -> List[str]:
    seat = str(seat_name or "").strip().lower()
    runtime = resolve_cards_runtime(issue=issue)
    artifact_contract = dict(runtime.get("artifact_contract") or {})
    review_paths = list(artifact_contract.get("review_read_paths") or [])
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


def required_write_paths_for_seat(*, seat_name: str, issue: Any) -> List[str]:
    seat = str(seat_name or "").strip().lower()
    runtime = resolve_cards_runtime(issue=issue)
    artifact_contract = dict(runtime.get("artifact_contract") or {})
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


def summarize_cards_runtime_issues(issue_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [dict(row) for row in issue_payloads if isinstance(row, dict)]
    if not rows:
        return {}
    profiles = sorted({str(row.get("execution_profile") or "").strip() for row in rows if str(row.get("execution_profile") or "").strip()})
    shared_profile = profiles[0] if len(profiles) == 1 else "mixed"
    odr_active = any(bool(row.get("odr_active")) for row in rows)
    summary = {
        "issues": rows,
        "execution_profile": shared_profile,
        "odr_active": odr_active,
    }
    if len(rows) == 1:
        row = rows[0]
        for key in (
            "builder_seat_choice",
            "reviewer_seat_choice",
            "seat_coercion",
            "artifact_contract",
            "odr_valid",
            "odr_pending_decisions",
            "odr_stop_reason",
            "odr_artifact_path",
        ):
            if key in row:
                summary[key] = row[key]
    return summary


def _resolve_base_profile(*, requested_profile: str, artifact_contract: Dict[str, Any]) -> str:
    if requested_profile in {APP_EXECUTION_PROFILE, ARTIFACT_EXECUTION_PROFILE}:
        return requested_profile
    if artifact_contract.get("kind") == "artifact":
        return ARTIFACT_EXECUTION_PROFILE
    return APP_EXECUTION_PROFILE


def _normalize_artifact_contract(value: Any) -> Dict[str, Any]:
    payload = dict(value or {}) if isinstance(value, dict) else {}
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
    return {
        "kind": kind,
        "primary_output": primary_output,
        "required_write_paths": write_paths,
        "required_read_paths": read_paths,
        "review_read_paths": review_read_paths,
        "entrypoint_path": entrypoint_path,
        "deployment_enabled": bool(kind == "app" and entrypoint_path == DEFAULT_APP_PRIMARY_OUTPUT),
    }


def _infer_contract_kind(primary_output: str, write_paths: List[str]) -> str:
    if primary_output == DEFAULT_APP_PRIMARY_OUTPUT and write_paths == [DEFAULT_APP_PRIMARY_OUTPUT]:
        return "app"
    return "artifact"


def _normalize_paths(*values: Any) -> List[str]:
    ordered: List[str] = []
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


def _normalize_odr_result(value: Any) -> Dict[str, Any]:
    payload = dict(value or {}) if isinstance(value, dict) else {}
    normalized: Dict[str, Any] = {}
    for key in (
        "odr_valid",
        "odr_pending_decisions",
        "odr_stop_reason",
        "odr_artifact_path",
        "odr_requirement",
        "odr_rounds_completed",
        "odr_accepted",
    ):
        if key not in payload:
            continue
        normalized[key] = payload[key]
    return normalized
