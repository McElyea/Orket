from __future__ import annotations

from typing import Any, Dict, List, Tuple


CANONICAL_PIPELINE_ROLES: Tuple[str, ...] = (
    "requirements_analyst",
    "architect",
    "coder",
    "code_reviewer",
    "integrity_guard",
)

CANONICAL_ROLE_REQUIRED_TOOLS: Dict[str, Tuple[str, ...]] = {
    "requirements_analyst": ("write_file", "update_issue_status"),
    "architect": ("write_file", "update_issue_status"),
    "coder": ("write_file", "update_issue_status"),
    "code_reviewer": ("read_file", "update_issue_status"),
    "integrity_guard": ("update_issue_status",),
}

CANONICAL_ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "requirements_analyst": {
        "intent": "Translate project asks into explicit, testable requirements for implementation handoff.",
        "responsibilities": [
            "Read issue context and existing artifacts before writing requirements.",
            "Write deterministic requirements to agent_output/requirements.txt.",
            "Call update_issue_status(status='code_review') after requirements are updated.",
        ],
        "constraints": [
            "Do not skip writing the requirements artifact.",
            "Keep acceptance criteria explicit and machine-checkable.",
        ],
    },
    "architect": {
        "intent": "Produce architecture decisions and implementation guidance aligned with requirements.",
        "responsibilities": [
            "Read requirements and relevant context before proposing architecture.",
            "Write design decisions to agent_output/design.txt.",
            "Call update_issue_status(status='code_review') after design artifact is updated.",
        ],
        "constraints": [
            "Keep architecture guidance deterministic and actionable.",
            "Do not skip required design artifact generation.",
        ],
    },
    "coder": {
        "intent": "Implement functional logic from architecture guidance with deterministic tool calls.",
        "responsibilities": [
            "Read required artifacts before implementation updates.",
            "Write implementation to agent_output/main.py.",
            "Call update_issue_status(status='code_review') after code updates.",
        ],
        "constraints": [
            "Do not bypass required implementation artifact writes.",
            "Keep output focused on executable changes and structured tool calls.",
        ],
    },
    "code_reviewer": {
        "intent": "Verify implementation against requirements, architecture, and runtime evidence.",
        "responsibilities": [
            "Read required artifacts and verification outputs before issuing a review decision.",
            "Record review rationale with concrete findings.",
            "Call update_issue_status(status='code_review') for integrity-guard handoff.",
        ],
        "constraints": [
            "Do not approve based on assumptions without reading required artifacts.",
            "Keep findings tied to concrete evidence.",
        ],
    },
    "integrity_guard": {
        "intent": "Enforce terminal governance decisions for completion readiness.",
        "responsibilities": [
            "Validate final artifacts and verification evidence against guard contracts.",
            "Produce deterministic terminal decisions using update_issue_status.",
            "When blocking, provide rationale and remediation expectations.",
        ],
        "constraints": [
            "Terminal status must be done or blocked.",
            "Do not skip guard decision emission for review turns.",
        ],
    },
}


def _as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def normalize_canonical_role_payload(role_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if role_name not in CANONICAL_ROLE_DEFAULTS:
        raise ValueError(f"Unsupported canonical role: {role_name}")

    raw = dict(payload or {})
    defaults = CANONICAL_ROLE_DEFAULTS[role_name]

    role_id = str(raw.get("id") or role_name.upper().replace("-", "_")).strip()
    name = str(raw.get("name") or raw.get("summary") or role_name).strip() or role_name
    role_type = str(raw.get("type") or "utility").strip() or "utility"
    description = str(raw.get("description") or "").strip() or f"{role_name} role."
    intent = str(raw.get("intent") or defaults["intent"]).strip() or defaults["intent"]
    responsibilities = _as_string_list(raw.get("responsibilities")) or list(defaults["responsibilities"])
    constraints = _as_string_list(raw.get("constraints")) or list(defaults["constraints"])
    tools = _as_string_list(raw.get("tools"))
    if not tools:
        tools = list(CANONICAL_ROLE_REQUIRED_TOOLS[role_name])

    normalized: Dict[str, Any] = {
        "id": role_id,
        "name": role_name if name != role_name else name,
        "type": role_type,
        "description": description,
        "intent": intent,
        "responsibilities": responsibilities,
        "constraints": constraints,
        "tools": tools,
        "prompt_metadata": dict(raw.get("prompt_metadata") or {}),
    }

    for optional_key in (
        "prompt",
        "policy",
        "capabilities",
        "labels",
        "references",
        "owner_department",
        "params",
    ):
        if optional_key in raw:
            normalized[optional_key] = raw[optional_key]

    known_keys = set(normalized.keys()) | {"summary"}
    extras = {k: v for k, v in raw.items() if k not in known_keys}
    for key in sorted(extras.keys()):
        normalized[key] = extras[key]

    return normalized


def canonical_role_conformance_violations(role_name: str, payload: Dict[str, Any]) -> List[Dict[str, str]]:
    if role_name not in CANONICAL_ROLE_DEFAULTS:
        return []

    violations: List[Dict[str, str]] = []

    role_type = str(payload.get("type") or "").strip().lower()
    if role_type != "utility":
        violations.append(
            {
                "code": "CANONICAL_ROLE_TYPE_INVALID",
                "message": "Canonical role type must be 'utility'.",
                "evidence": str(payload.get("type") or ""),
            }
        )

    name = str(payload.get("name") or payload.get("summary") or "").strip()
    if name != role_name:
        violations.append(
            {
                "code": "CANONICAL_ROLE_NAME_DRIFT",
                "message": f"Canonical role name must match file stem '{role_name}'.",
                "evidence": name or "",
            }
        )

    description = str(payload.get("description") or "").strip()
    if not description:
        violations.append(
            {
                "code": "CANONICAL_ROLE_DESCRIPTION_MISSING",
                "message": "Canonical role description must be non-empty.",
                "evidence": "",
            }
        )

    intent = str(payload.get("intent") or "").strip()
    if not intent:
        violations.append(
            {
                "code": "CANONICAL_ROLE_INTENT_MISSING",
                "message": "Canonical role intent must be non-empty.",
                "evidence": "",
            }
        )

    responsibilities = _as_string_list(payload.get("responsibilities"))
    if not responsibilities:
        violations.append(
            {
                "code": "CANONICAL_ROLE_RESPONSIBILITIES_MISSING",
                "message": "Canonical role responsibilities must be a non-empty string list.",
                "evidence": "",
            }
        )

    constraints = _as_string_list(payload.get("constraints"))
    if not constraints:
        violations.append(
            {
                "code": "CANONICAL_ROLE_CONSTRAINTS_MISSING",
                "message": "Canonical role constraints must be a non-empty string list.",
                "evidence": "",
            }
        )

    tools = set(_as_string_list(payload.get("tools")))
    required = set(CANONICAL_ROLE_REQUIRED_TOOLS.get(role_name, ()))
    missing_tools = sorted(required - tools)
    if missing_tools:
        violations.append(
            {
                "code": "CANONICAL_ROLE_REQUIRED_TOOLS_MISSING",
                "message": f"Canonical role is missing required tools: {missing_tools}.",
                "evidence": ",".join(missing_tools),
            }
        )

    return violations
