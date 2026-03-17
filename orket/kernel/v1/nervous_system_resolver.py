from __future__ import annotations

from typing import Any

from .nervous_system_policy import is_exfil_payload


KNOWN_TOOL_PROFILES = {
    "fs.delete": {"risk": "critical", "destructive": True, "credentialed": False, "exfil": False},
    "fs.write_patch": {"risk": "high", "destructive": True, "credentialed": False, "exfil": False},
    "demo.credentialed_echo": {"risk": "high", "destructive": False, "credentialed": True, "exfil": False},
    "demo.exfil_http": {"risk": "high", "destructive": False, "credentialed": False, "exfil": True},
    "local.echo": {"risk": "low", "destructive": False, "credentialed": False, "exfil": False},
}


def resolve_tool_policy_flags(payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name") or "").strip()
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}

    resolved = {
        "policy_forbidden": False,
        "scope_violation": False,
        "unknown_tool_profile": False,
        "approval_required_destructive": False,
        "approval_required_exfil": False,
        "approval_required_credentialed": False,
    }

    profile = KNOWN_TOOL_PROFILES.get(tool_name)
    if profile is None:
        resolved["unknown_tool_profile"] = True
        return resolved

    if bool(profile.get("destructive")):
        resolved["approval_required_destructive"] = True
    if bool(profile.get("credentialed")):
        resolved["approval_required_credentialed"] = True
    if bool(profile.get("exfil")):
        resolved["approval_required_exfil"] = True

    if tool_name == "fs.delete":
        target = str(args.get("path") or "")
        # Locked harness behavior: deleting protected local path is out of scope.
        if target.replace("\\", "/").endswith("workspace/important.txt"):
            resolved["scope_violation"] = True

    if is_exfil_payload(payload):
        resolved["approval_required_exfil"] = True

    return resolved


__all__ = ["KNOWN_TOOL_PROFILES", "resolve_tool_policy_flags"]
