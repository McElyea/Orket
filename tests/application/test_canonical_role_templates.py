from __future__ import annotations

from orket.application.services.canonical_role_templates import (
    canonical_role_conformance_violations,
    normalize_canonical_role_payload,
)


def test_normalize_canonical_role_payload_fills_structure_defaults() -> None:
    payload = {
        "id": "ARCHITECT",
        "summary": "architect",
        "type": "utility",
        "description": "Architect role.",
        "tools": ["write_file", "update_issue_status"],
        "prompt_metadata": {"id": "role.architect"},
    }
    normalized = normalize_canonical_role_payload("architect", payload)

    assert normalized["name"] == "architect"
    assert normalized["intent"]
    assert isinstance(normalized["responsibilities"], list) and normalized["responsibilities"]
    assert isinstance(normalized["constraints"], list) and normalized["constraints"]


def test_canonical_role_conformance_violations_reports_missing_required_tools() -> None:
    payload = {
        "name": "code_reviewer",
        "type": "utility",
        "description": "Review role.",
        "intent": "Review implementation artifacts.",
        "responsibilities": ["Review code."],
        "constraints": ["No assumptions."],
        "tools": ["update_issue_status"],
    }
    violations = canonical_role_conformance_violations("code_reviewer", payload)

    codes = {item["code"] for item in violations}
    assert "CANONICAL_ROLE_REQUIRED_TOOLS_MISSING" in codes


def test_canonical_role_conformance_violations_pass_for_normalized_role() -> None:
    normalized = normalize_canonical_role_payload(
        "requirements_analyst",
        {
            "id": "REQUIREMENTS_ANALYST",
            "name": "requirements_analyst",
            "type": "utility",
            "description": "Requirements role.",
            "tools": ["read_file", "write_file", "update_issue_status"],
            "prompt_metadata": {"id": "role.requirements_analyst"},
        },
    )
    violations = canonical_role_conformance_violations("requirements_analyst", normalized)
    assert violations == []
