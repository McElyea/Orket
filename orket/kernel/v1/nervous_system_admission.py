"""Admission decision evaluation over explicitly selected operator policy."""
from __future__ import annotations

from typing import Any

from .nervous_system_contract import ordered_reason_codes_v1
from .nervous_system_leaks import find_leak_hits
from .nervous_system_policy import NervousSystemPolicyInputs, is_exfil_payload
from .nervous_system_resolver import resolve_tool_policy_flags

_POLICY_FLAG_KEYS = (
    "policy_forbidden",
    "scope_violation",
    "unknown_tool_profile",
    "approval_required_destructive",
    "approval_required_exfil",
    "approval_required_credentialed",
)


def admission_from_proposal(
    proposal: dict[str, Any], policy_inputs: NervousSystemPolicyInputs,
) -> tuple[str, list[str], list[str]]:
    proposal_type = proposal.get("proposal_type")
    if proposal_type != "action.tool_call":
        return "REJECT", ["SCHEMA_INVALID"], []

    payload = proposal.get("payload")
    if not isinstance(payload, dict):
        return "REJECT", ["SCHEMA_INVALID"], []

    effective_payload = dict(payload)
    if policy_inputs.use_profile_resolver:
        resolved_flags = resolve_tool_policy_flags(payload)
        for key in _POLICY_FLAG_KEYS:
            effective_payload[key] = bool(payload.get(key)) or bool(resolved_flags.get(key))
    elif not policy_inputs.allow_pre_resolved_flags:
        effective_payload["unknown_tool_profile"] = True
        effective_payload["policy_forbidden"] = False
        effective_payload["scope_violation"] = False
        effective_payload["approval_required_destructive"] = False
        effective_payload["approval_required_exfil"] = False
        effective_payload["approval_required_credentialed"] = False

    if bool(effective_payload.get("policy_forbidden")):
        return "REJECT", ["POLICY_FORBIDDEN"], []

    leak_hits = find_leak_hits(payload.get("outbound_payload", payload))
    if bool(effective_payload.get("leak_detected")) or (leak_hits and is_exfil_payload(effective_payload)):
        return "REJECT", ["LEAK_DETECTED"], leak_hits

    if bool(effective_payload.get("scope_violation")):
        return "REJECT", ["SCOPE_VIOLATION"], []

    if bool(effective_payload.get("unknown_tool_profile")):
        return "NEEDS_APPROVAL", ["UNKNOWN_TOOL_PROFILE"], []

    approval_reasons: list[str] = []
    if bool(effective_payload.get("approval_required_destructive")):
        approval_reasons.append("APPROVAL_REQUIRED_DESTRUCTIVE")
    if bool(effective_payload.get("approval_required_exfil")) or is_exfil_payload(effective_payload):
        approval_reasons.append("APPROVAL_REQUIRED_EXFIL")
    if bool(effective_payload.get("approval_required_credentialed")):
        approval_reasons.append("APPROVAL_REQUIRED_CREDENTIALED")
    if approval_reasons:
        return "NEEDS_APPROVAL", ordered_reason_codes_v1(approval_reasons), []

    return "ACCEPT_TO_UNIFY", [], []
