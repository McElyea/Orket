from __future__ import annotations

import json
from typing import Any

from .models import (
    DeterministicAnalysisArtifact,
    ForbiddenOperationHit,
    ResourceChangeRecord,
    canonical_digest,
)


def digest_plan_bytes(raw_bytes: bytes) -> str:
    return canonical_digest({"plan_bytes_utf8": raw_bytes.decode("utf-8", errors="replace")})


def parse_plan_json(raw_bytes: bytes) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "invalid_json_plan"
    if not isinstance(payload, dict):
        return None, "invalid_json_root"
    return payload, ""


def _normalized_action(actions: Any) -> str:
    if not isinstance(actions, list) or not actions:
        return ""
    normalized = [str(item).strip().lower() for item in actions if str(item).strip()]
    if normalized == ["create"]:
        return "create"
    if normalized == ["update"]:
        return "update"
    if normalized == ["delete"]:
        return "destroy"
    if normalized == ["no-op"] or normalized == ["noop"]:
        return "no-op"
    if normalized in (["delete", "create"], ["create", "delete"]):
        return "replace"
    return ""


def analyze_plan(*, plan_payload: dict[str, Any], forbidden_operations: list[str]) -> DeterministicAnalysisArtifact:
    warnings: list[str] = []
    resource_changes: list[ResourceChangeRecord] = []
    forbidden_hits: list[ForbiddenOperationHit] = []
    action_counts = {"create": 0, "update": 0, "destroy": 0, "replace": 0, "no-op": 0}
    analysis_complete = True
    forbidden = {str(item).strip().lower() for item in forbidden_operations if str(item).strip()}

    rows = plan_payload.get("resource_changes")
    if not isinstance(rows, list):
        return DeterministicAnalysisArtifact(
            analysis_complete=False,
            resource_changes=[],
            action_counts=action_counts,
            forbidden_operation_hits=[],
            warnings=["resource_changes_missing_or_invalid"],
            analysis_confidence="incomplete",
        )

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            analysis_complete = False
            warnings.append(f"resource_change_invalid:{index}")
            continue
        address = str(row.get("address") or "").strip()
        provider_name = str(row.get("provider_name") or "").strip()
        resource_type = str(row.get("type") or "").strip()
        change_payload = row.get("change")
        action = _normalized_action(change_payload.get("actions") if isinstance(change_payload, dict) else None)
        if not address or not resource_type or not action:
            analysis_complete = False
            warnings.append(f"resource_change_incomplete:{index}")
            continue
        record = ResourceChangeRecord(
            address=address,
            provider_name=provider_name,
            resource_type=resource_type,
            action=action,
        )
        resource_changes.append(record)
        action_counts[action] = int(action_counts.get(action, 0)) + 1
        if action in forbidden:
            forbidden_hits.append(
                ForbiddenOperationHit(
                    operation=action,
                    address=address,
                    provider_name=provider_name,
                    resource_type=resource_type,
                )
            )

    if not resource_changes and rows:
        analysis_complete = False

    return DeterministicAnalysisArtifact(
        analysis_complete=analysis_complete,
        resource_changes=resource_changes,
        action_counts=action_counts,
        forbidden_operation_hits=forbidden_hits,
        warnings=warnings,
        analysis_confidence="complete" if analysis_complete else "incomplete",
    )
