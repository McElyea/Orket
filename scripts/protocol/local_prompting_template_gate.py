"""Fail-closed binding between template audit, approval and measured render evidence."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def profile_row_hash(row: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def template_gate(
    audit: dict[str, Any] | None,
    approval: dict[str, Any] | None,
    render: dict[str, Any],
    profile_row: dict[str, Any],
) -> tuple[bool, str]:
    audit, approval = audit or {}, approval or {}
    digest = str(audit.get("template_sha256") or "")
    identity = str(profile_row.get("profile", {}).get("profile_id") or "")
    bound = bool(
        identity
        and audit.get("profile_id") == identity
        and audit.get("profile_row_sha256") == profile_row_hash(profile_row)
        and len(digest) == 64
        and audit.get("template_bytes", 0) > 0
        and render.get("verified")
        and render.get("template_source_sha256") == digest
        and render.get("method") == "provider_native_preview_byte_exact"
    )
    approved = bool(
        approval.get("approved")
        and approval.get("promotion_allowed")
        and approval.get("profile_id") == identity
        and approval.get("template_sha256") == digest
        and approval.get("approval_reference")
        and approval.get("approved_by")
    )
    clean = audit.get("decision") == "pass" and not audit.get("detected_constructs")
    return bound and (clean or approved), f"template_render_bound={bound} clean={clean} approved={approved}"


def profile_template_family(snapshot_payload: dict[str, Any], profile_id: str) -> str:
    rows = snapshot_payload.get("profiles")
    if not isinstance(rows, list):
        return "unknown"
    for row in rows:
        if not isinstance(row, dict):
            continue
        profile = row.get("profile")
        if not isinstance(profile, dict):
            continue
        if str(profile.get("profile_id") or "") != profile_id:
            continue
        return str(profile.get("template_family") or "unknown")
    return "unknown"
