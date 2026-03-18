from __future__ import annotations

from typing import Any

from .canonical import LSI_VERSION_V1, digest_of
from .nervous_system_contract import tool_profile_digest
from .nervous_system_resolver import KNOWN_TOOL_PROFILES

SNAPSHOT_SCHEMA_VERSION = 1
SNAPSHOT_VERSION = "nervous_system_policy_digest_snapshot/v2"
DIGEST_ALGORITHM = "sha256"
CANONICALIZER = f"orket/kernel/v1/canonical.py@{LSI_VERSION_V1}"
POLICY_CONTEXT_SOURCE_PATH = "orket/kernel/v1/nervous_system_policy_snapshot.py"
DENY_RULE_SOURCE_PATH = "orket/kernel/v1/nervous_system_policy_snapshot.py"
TOOL_PROFILE_SOURCE_PATH = "orket/kernel/v1/nervous_system_resolver.py"

POLICY_CONTEXTS: dict[str, dict[str, Any]] = {
    "strict_default": {"mode": "strict"},
}

DENY_RULE_EXAMPLES: dict[str, dict[str, Any]] = {
    "deny_ssh_private_key_read": {
        "rule_id": "deny_ssh_private_key_read",
        "tool_name": "fs.read",
        "target_path_glob": "**/.ssh/**",
        "reason_code": "POLICY_FORBIDDEN",
    }
}


def _tool_profile_definition(tool_name: str, profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": tool_name,
        "risk": profile.get("risk"),
        "destructive": bool(profile.get("destructive")),
        "credentialed": bool(profile.get("credentialed")),
        "exfil": bool(profile.get("exfil")),
    }


def build_policy_digest_snapshot() -> dict[str, Any]:
    policy_context_digest_expectations = {name: digest_of(context) for name, context in sorted(POLICY_CONTEXTS.items())}

    deny_rule_digest_expectations = {name: digest_of(rule) for name, rule in sorted(DENY_RULE_EXAMPLES.items())}

    tool_profile_digest_expectations = {
        tool_name: tool_profile_digest(_tool_profile_definition(tool_name, profile))
        for tool_name, profile in sorted(KNOWN_TOOL_PROFILES.items())
    }

    return {
        "snapshot_version": SNAPSHOT_SCHEMA_VERSION,
        "version": SNAPSHOT_VERSION,
        "digest_algorithm": DIGEST_ALGORITHM,
        "canonicalizer": CANONICALIZER,
        "policy_context_digest_expectations": policy_context_digest_expectations,
        "deny_rule_digest_expectations": deny_rule_digest_expectations,
        "tool_profile_digest_expectations": tool_profile_digest_expectations,
    }


def build_policy_digest_contributors() -> dict[str, list[dict[str, str]]]:
    policy_contexts = [
        {
            "name": name,
            "digest": digest_of(context),
            "source_path": POLICY_CONTEXT_SOURCE_PATH,
            "rule_name": name,
        }
        for name, context in sorted(POLICY_CONTEXTS.items())
    ]
    deny_rules = [
        {
            "name": name,
            "digest": digest_of(rule),
            "source_path": DENY_RULE_SOURCE_PATH,
            "rule_name": str(rule.get("rule_id") or name),
        }
        for name, rule in sorted(DENY_RULE_EXAMPLES.items())
    ]
    tool_profiles = [
        {
            "name": tool_name,
            "digest": tool_profile_digest(_tool_profile_definition(tool_name, profile)),
            "source_path": TOOL_PROFILE_SOURCE_PATH,
            "rule_name": tool_name,
        }
        for tool_name, profile in sorted(KNOWN_TOOL_PROFILES.items())
    ]
    return {
        "policy_contexts": policy_contexts,
        "deny_rules": deny_rules,
        "tool_profiles": tool_profiles,
    }


__all__ = [
    "CANONICALIZER",
    "DENY_RULE_EXAMPLES",
    "DENY_RULE_SOURCE_PATH",
    "DIGEST_ALGORITHM",
    "POLICY_CONTEXT_SOURCE_PATH",
    "POLICY_CONTEXTS",
    "SNAPSHOT_VERSION",
    "SNAPSHOT_SCHEMA_VERSION",
    "TOOL_PROFILE_SOURCE_PATH",
    "build_policy_digest_contributors",
    "build_policy_digest_snapshot",
]
