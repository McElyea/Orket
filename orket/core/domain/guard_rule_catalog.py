from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Literal, Tuple


GuardOwner = Literal["hallucination", "security", "consistency"]
GuardSeverity = Literal["soft", "strict"]
GuardScope = Literal["system", "user", "context", "output"]


@dataclass(frozen=True)
class GuardRule:
    rule_id: str
    owner: GuardOwner
    description: str
    severity: GuardSeverity
    scope: Tuple[GuardScope, ...]


DEFAULT_GUARD_RULES: List[GuardRule] = [
    GuardRule(
        rule_id="HALLUCINATION.FILE_NOT_FOUND",
        owner="hallucination",
        description="Referenced file is not present in verification scope workspace.",
        severity="strict",
        scope=("output",),
    ),
    GuardRule(
        rule_id="HALLUCINATION.API_NOT_DECLARED",
        owner="hallucination",
        description="Referenced API/interface is not present in declared interfaces.",
        severity="strict",
        scope=("output",),
    ),
    GuardRule(
        rule_id="HALLUCINATION.CONTEXT_NOT_PROVIDED",
        owner="hallucination",
        description="Referenced context is not present in provided context scope.",
        severity="strict",
        scope=("output", "context"),
    ),
    GuardRule(
        rule_id="HALLUCINATION.INVENTED_DETAIL",
        owner="hallucination",
        description="Output introduces details not grounded in provided inputs.",
        severity="strict",
        scope=("output", "context"),
    ),
    GuardRule(
        rule_id="HALLUCINATION.CONTRADICTION",
        owner="hallucination",
        description="Output contradicts provided user or system context.",
        severity="strict",
        scope=("output", "user", "system", "context"),
    ),
    GuardRule(
        rule_id="SECURITY.PATH_TRAVERSAL",
        owner="security",
        description="Output or tool call attempts path traversal or unsafe path access.",
        severity="strict",
        scope=("output",),
    ),
    GuardRule(
        rule_id="CONSISTENCY.OUTPUT_FORMAT",
        owner="consistency",
        description="Output does not conform to required format or schema contract.",
        severity="strict",
        scope=("output",),
    ),
]


DEFAULT_GUARD_RULE_IDS: List[str] = [
    rule.rule_id for rule in DEFAULT_GUARD_RULES
]


def normalize_rule_ids(values: Iterable[object] | None) -> List[str]:
    if values is None:
        return []
    normalized: List[str] = []
    seen = set()
    for value in values:
        rule_id = str(value or "").strip()
        if not rule_id:
            continue
        if rule_id in seen:
            continue
        seen.add(rule_id)
        normalized.append(rule_id)
    return normalized


def ownership_conflicts(prompt_rule_ids: Iterable[object] | None, runtime_guard_rule_ids: Iterable[object] | None) -> List[str]:
    prompt_ids = set(normalize_rule_ids(prompt_rule_ids))
    runtime_ids = set(normalize_rule_ids(runtime_guard_rule_ids))
    return sorted(prompt_ids.intersection(runtime_ids))


def build_guard_rule_registry(rules: Iterable[GuardRule] | None = None) -> Dict[str, GuardRule]:
    source = list(DEFAULT_GUARD_RULES if rules is None else rules)
    registry: Dict[str, GuardRule] = {}
    for rule in source:
        rule_id = str(rule.rule_id or "").strip()
        if not rule_id:
            raise ValueError("guard rule_id cannot be empty")
        if rule_id in registry:
            raise ValueError(f"duplicate guard rule_id: {rule_id}")
        if not rule.scope:
            raise ValueError(f"guard rule '{rule_id}' must declare at least one scope location")
        expected_prefix = f"{rule.owner.upper()}."
        if not rule_id.startswith(expected_prefix):
            raise ValueError(
                f"guard rule '{rule_id}' owner '{rule.owner}' must use prefix '{expected_prefix}'"
            )
        registry[rule_id] = rule
    return registry


DEFAULT_GUARD_RULE_REGISTRY: Dict[str, GuardRule] = build_guard_rule_registry()
GUARD_OWNER_PREFIXES: Tuple[str, ...] = ("HALLUCINATION.", "SECURITY.", "CONSISTENCY.")


def validate_runtime_guard_rule_ids(
    runtime_guard_rule_ids: Iterable[object] | None,
    *,
    registry: Dict[str, GuardRule] | None = None,
) -> List[str]:
    if runtime_guard_rule_ids is None:
        return []
    raw_values = [
        str(value or "").strip()
        for value in runtime_guard_rule_ids
        if str(value or "").strip()
    ]
    if len(raw_values) != len(set(raw_values)):
        seen = set()
        duplicates: List[str] = []
        for item in raw_values:
            if item in seen and item not in duplicates:
                duplicates.append(item)
            seen.add(item)
        raise ValueError("Duplicate runtime guard rule_id values: " + ", ".join(sorted(duplicates)))
    normalized = normalize_rule_ids(raw_values)
    if not normalized:
        return []
    registry = registry or DEFAULT_GUARD_RULE_REGISTRY
    unknown = sorted(rule_id for rule_id in normalized if rule_id not in registry)
    if unknown:
        raise ValueError(
            "Unknown runtime guard rule_id values: " + ", ".join(unknown)
        )
    return normalized


def resolve_runtime_guard_rule_ids(
    configured_rule_ids: Iterable[object] | None,
    *,
    registry: Dict[str, GuardRule] | None = None,
) -> List[str]:
    if configured_rule_ids is None:
        return list(DEFAULT_GUARD_RULE_IDS)
    validated = validate_runtime_guard_rule_ids(
        configured_rule_ids,
        registry=registry,
    )
    return validated if validated else list(DEFAULT_GUARD_RULE_IDS)


def prompt_guard_namespace_conflicts(prompt_rule_ids: Iterable[object] | None) -> List[str]:
    prompt_ids = normalize_rule_ids(prompt_rule_ids)
    return sorted(
        rule_id
        for rule_id in prompt_ids
        if any(rule_id.startswith(prefix) for prefix in GUARD_OWNER_PREFIXES)
    )
