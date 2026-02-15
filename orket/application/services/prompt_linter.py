from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Literal

from pydantic import ValidationError

from orket.application.services.canonical_role_templates import (
    CANONICAL_PIPELINE_ROLES,
    canonical_role_conformance_violations,
)
from orket.schema import DialectConfig, RoleConfig

VALID_STATUSES = {"draft", "candidate", "canary", "stable", "deprecated"}

LintSeverity = Literal["soft", "strict"]
LintLocation = Literal["system", "user", "context", "output"]


def _violation(
    *,
    file: Path,
    rule_id: str,
    code: str,
    message: str,
    location: LintLocation = "system",
    severity: LintSeverity = "strict",
    evidence: str | None = None,
) -> Dict[str, Any]:
    return {
        "file": str(file),
        "rule_id": rule_id,
        "code": code,
        "message": message,
        "location": location,
        "severity": severity,
        "evidence": evidence,
    }


def _extract_placeholders(text: str) -> List[str]:
    return sorted({m.group(1).strip() for m in re.finditer(r"\{\{\s*([^{}]+?)\s*\}\}", text or "") if m.group(1).strip()})


def _collect_unbalanced_placeholder_violations(text: str, path: Path, field: str) -> List[Dict[str, Any]]:
    if "{{" not in text:
        return []
    if "}}" in text and text.count("{{") == text.count("}}"):
        return []
    return [
        _violation(
            file=path,
            rule_id="PL002",
            code="PLACEHOLDER_UNBALANCED",
            message=f"{field} has unbalanced placeholder delimiters.",
            location="user",
            severity="strict",
            evidence=field,
        )
    ]


def _prompt_text_fields(payload: Dict[str, Any]) -> List[tuple[str, str]]:
    fields: List[tuple[str, str]] = []
    for key in ("prompt", "description", "dsl_format", "hallucination_guard", "system_prefix"):
        value = payload.get(key)
        if isinstance(value, str):
            fields.append((key, value))
    constraints = payload.get("constraints")
    if isinstance(constraints, list):
        for idx, value in enumerate(constraints):
            if isinstance(value, str):
                fields.append((f"constraints[{idx}]", value))
    return fields


def lint_prompt_asset(path: Path, payload: Dict[str, Any], kind: str) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []

    try:
        if kind == "role":
            RoleConfig.model_validate(payload)
        elif kind == "dialect":
            DialectConfig.model_validate(payload)
        else:
            raise ValueError(f"Unsupported kind: {kind}")
    except (ValidationError, ValueError) as exc:
        violations.append(
            _violation(
                file=path,
                rule_id="PL001",
                code="SCHEMA_INVALID",
                message=f"Asset failed schema validation: {exc}",
                location="system",
                severity="strict",
            )
        )
        return violations

    metadata = payload.get("prompt_metadata")
    if not isinstance(metadata, dict):
        return [
            _violation(
                file=path,
                rule_id="PL005",
                code="PROMPT_METADATA_MISSING",
                message="prompt_metadata must be an object.",
                location="system",
                severity="strict",
            )
        ]

    prompt_id = str(metadata.get("id") or "").strip()
    version = str(metadata.get("version") or "").strip()
    status = str(metadata.get("status") or "").strip()
    owner = str(metadata.get("owner") or "").strip()
    updated_at = str(metadata.get("updated_at") or "").strip()
    expected_id = f"{kind}.{path.stem}"
    if prompt_id != expected_id:
        violations.append(
            _violation(
                file=path,
                rule_id="PL005",
                code="PROMPT_ID_MISMATCH",
                message=f"prompt_metadata.id must equal '{expected_id}' (got '{prompt_id}').",
                location="system",
                severity="strict",
                evidence=prompt_id or None,
            )
        )
    if not version:
        violations.append(
            _violation(file=path, rule_id="PL005", code="VERSION_MISSING", message="prompt_metadata.version is required.")
        )
    if status not in VALID_STATUSES:
        violations.append(
            _violation(
                file=path,
                rule_id="PL005",
                code="STATUS_INVALID",
                message=f"prompt_metadata.status must be one of {sorted(VALID_STATUSES)}.",
                evidence=status or None,
            )
        )
    if not owner:
        violations.append(
            _violation(file=path, rule_id="PL005", code="OWNER_MISSING", message="prompt_metadata.owner is required.")
        )
    if not updated_at:
        violations.append(
            _violation(file=path, rule_id="PL005", code="UPDATED_AT_MISSING", message="prompt_metadata.updated_at is required.")
        )

    lineage = metadata.get("lineage")
    if not isinstance(lineage, dict):
        violations.append(
            _violation(file=path, rule_id="PL005", code="LINEAGE_INVALID", message="prompt_metadata.lineage must be an object.")
        )

    changelog = metadata.get("changelog")
    if not isinstance(changelog, list) or not changelog:
        violations.append(
            _violation(
                file=path,
                rule_id="PL005",
                code="CHANGELOG_INVALID",
                message="prompt_metadata.changelog must be a non-empty list.",
            )
        )
    else:
        versions = set()
        for idx, entry in enumerate(changelog):
            if not isinstance(entry, dict):
                violations.append(
                    _violation(
                        file=path,
                        rule_id="PL005",
                        code="CHANGELOG_ENTRY_INVALID",
                        message=f"prompt_metadata.changelog[{idx}] must be an object.",
                    )
                )
                continue
            v = str(entry.get("version") or "").strip()
            d = str(entry.get("date") or "").strip()
            n = str(entry.get("notes") or "").strip()
            if not v:
                violations.append(_violation(file=path, rule_id="PL005", code="CHANGELOG_VERSION_MISSING", message=f"prompt_metadata.changelog[{idx}].version missing."))
            if not d:
                violations.append(_violation(file=path, rule_id="PL005", code="CHANGELOG_DATE_MISSING", message=f"prompt_metadata.changelog[{idx}].date missing."))
            if not n:
                violations.append(_violation(file=path, rule_id="PL005", code="CHANGELOG_NOTES_MISSING", message=f"prompt_metadata.changelog[{idx}].notes missing."))
            if v:
                versions.add(v)
        if version and version not in versions:
            violations.append(
                _violation(
                    file=path,
                    rule_id="PL005",
                    code="VERSION_NOT_IN_CHANGELOG",
                    message=f"prompt_metadata.version '{version}' missing from changelog entries.",
                    evidence=version,
                )
            )

    declared_placeholders = metadata.get("placeholders")
    declared = set()
    if isinstance(declared_placeholders, list):
        declared = {str(item).strip() for item in declared_placeholders if str(item).strip()}

    found_placeholders = set()
    for field_name, text in _prompt_text_fields(payload):
        violations.extend(_collect_unbalanced_placeholder_violations(text, path, field_name))
        for placeholder in _extract_placeholders(text):
            found_placeholders.add(placeholder)

    if declared:
        undeclared = sorted(item for item in found_placeholders if item not in declared)
        for placeholder in undeclared:
            violations.append(
                _violation(
                    file=path,
                    rule_id="PL002",
                    code="PLACEHOLDER_UNDECLARED",
                    message=f"Placeholder '{{{{{placeholder}}}}}' not declared in prompt_metadata.placeholders.",
                    location="user",
                    severity="strict",
                    evidence=placeholder,
                )
            )
        unused = sorted(item for item in declared if item not in found_placeholders)
        for placeholder in unused:
            violations.append(
                _violation(
                    file=path,
                    rule_id="PL002",
                    code="PLACEHOLDER_UNUSED",
                    message=f"Declared placeholder '{placeholder}' is not used in prompt text fields.",
                    location="user",
                    severity="soft",
                    evidence=placeholder,
                )
            )

    if kind == "role" and path.stem in CANONICAL_PIPELINE_ROLES:
        for item in canonical_role_conformance_violations(path.stem, payload):
            violations.append(
                _violation(
                    file=path,
                    rule_id="PL006",
                    code=str(item.get("code") or "CANONICAL_ROLE_DRIFT"),
                    message=str(item.get("message") or "Canonical role structure drift detected."),
                    location="system",
                    severity="strict",
                    evidence=str(item.get("evidence") or "") or None,
                )
            )

    return violations


def lint_prompt_file(path: Path, kind: str) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            _violation(
                file=path,
                rule_id="PL001",
                code="JSON_INVALID",
                message=f"invalid JSON ({exc})",
                location="system",
                severity="strict",
            )
        ]
    return lint_prompt_asset(path, payload, kind)
