from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Mapping


TRUTHFUL_MEMORY_POLICY_SCHEMA_VERSION = "truthful_memory_policy.v1"

MemoryClass = Literal["working_memory", "durable_memory", "reference_context"]
MemoryTrustLevel = Literal["authoritative", "advisory", "stale_risk", "unverified"]
MemoryConflictResolution = Literal[
    "none",
    "no_change",
    "setting_update",
    "user_correction",
    "stale_update_rejected",
    "contradiction_requires_correction",
]

_ALLOWED_TRUST_LEVELS = {"authoritative", "advisory", "stale_risk", "unverified"}
_ALLOWED_CONFLICT_RESOLUTIONS = {
    "none",
    "no_change",
    "setting_update",
    "user_correction",
    "stale_update_rejected",
    "contradiction_requires_correction",
}
_SESSION_RATIONALES = {
    "chat_input": "session_user_turn_capture",
    "chat_output": "session_assistant_turn_capture",
}
_REFERENCE_RATIONALES = {
    "decision": "reference_decision_capture",
    "episodic_turn": "episodic_turn_summary_capture",
}


@dataclass(frozen=True)
class MemoryWritePolicyDecision:
    allow_write: bool
    metadata: dict[str, Any]
    conflict_resolution: MemoryConflictResolution
    error_code: str | None = None
    error_message: str = ""


def truthful_memory_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": TRUTHFUL_MEMORY_POLICY_SCHEMA_VERSION,
        "memory_classes": {
            "working_memory": {
                "scopes": ["session_memory"],
                "default_write_threshold": "session_turn_capture",
                "trust_defaults": {
                    "chat_input": "authoritative",
                    "chat_output": "advisory",
                },
            },
            "durable_memory": {
                "scopes": ["profile_memory"],
                "default_write_thresholds": {
                    "user_preference.": "explicit_preference_persist",
                    "user_fact.": "confirmed_user_fact",
                    "companion_setting.": "profile_setting_persist",
                    "companion_mode.": "profile_setting_persist",
                },
                "conflict_rules": {
                    "user_correction_required_on_contradiction": True,
                    "stale_updates_fail_closed": True,
                },
            },
            "reference_context": {
                "scopes": ["episodic_memory", "project_memory"],
                "default_write_threshold": "reference_context_capture",
                "default_trust_level": "advisory",
            },
        },
        "trust_levels": {
            "authoritative": "trusted for governed synthesis without downgrade.",
            "advisory": "included in governed synthesis but must remain labeled as advisory.",
            "stale_risk": "excluded from governed synthesis unless explicitly refreshed.",
            "unverified": "excluded from governed synthesis until provenance improves.",
        },
        "governed_synthesis": {
            "include": ["authoritative", "advisory"],
            "exclude": ["stale_risk", "unverified"],
        },
    }


def memory_class_for_scope(scope: str) -> MemoryClass:
    normalized_scope = str(scope or "").strip().lower()
    if normalized_scope == "session_memory":
        return "working_memory"
    if normalized_scope == "profile_memory":
        return "durable_memory"
    return "reference_context"


def evaluate_memory_write_policy(
    *,
    scope: str,
    key: str,
    value: str,
    metadata: Mapping[str, Any] | None = None,
    existing_value: str | None = None,
    existing_metadata: Mapping[str, Any] | None = None,
) -> MemoryWritePolicyDecision:
    scope_name = str(scope or "").strip().lower()
    key_name = str(key or "").strip()
    value_text = str(value or "")
    metadata_payload = dict(metadata or {})
    metadata_payload["memory_class"] = memory_class_for_scope(scope_name)
    metadata_payload["memory_policy_version"] = TRUTHFUL_MEMORY_POLICY_SCHEMA_VERSION

    if scope_name == "session_memory":
        return _evaluate_session_write(metadata_payload)
    if scope_name == "profile_memory":
        return _evaluate_profile_write(
            key=key_name,
            value=value_text,
            metadata=metadata_payload,
            existing_value=str(existing_value or ""),
            existing_metadata=dict(existing_metadata or {}),
        )
    return _evaluate_reference_write(metadata_payload)


def classify_memory_trust_level(
    *,
    scope: str,
    metadata: Mapping[str, Any] | None = None,
    timestamp: str = "",
) -> MemoryTrustLevel:
    metadata_payload = dict(metadata or {})
    if _is_stale(metadata_payload, fallback_timestamp=timestamp):
        return "stale_risk"

    explicit = str(metadata_payload.get("trust_level") or "").strip().lower()
    if explicit in _ALLOWED_TRUST_LEVELS and explicit != "stale_risk":
        return explicit  # type: ignore[return-value]

    resolved_class = str(metadata_payload.get("memory_class") or memory_class_for_scope(scope))
    kind = str(metadata_payload.get("kind") or metadata_payload.get("type") or "").strip().lower()
    if resolved_class == "durable_memory":
        return "authoritative"
    if resolved_class == "working_memory":
        return "authoritative" if kind == "chat_input" else "advisory"
    if resolved_class == "reference_context":
        return "advisory" if (timestamp or metadata_payload) else "unverified"
    return "unverified"


def synthesis_disposition_for_trust_level(trust_level: str) -> str:
    return "include" if str(trust_level or "").strip().lower() in {"authoritative", "advisory"} else "exclude"


def render_reference_context_rows(rows: list[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    for row in rows:
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        metadata = dict(row.get("metadata") or {})
        trust_level = classify_memory_trust_level(
            scope="project_memory",
            metadata=metadata,
            timestamp=str(row.get("timestamp") or ""),
        )
        if synthesis_disposition_for_trust_level(trust_level) == "exclude":
            continue
        lines.append(f"- [reference_context][trust={trust_level}] {content}")
    return "\n".join(lines)


def render_scoped_memory_rows(rows: list[Any], *, prefix: str) -> list[str]:
    rendered: list[str] = []
    for row in rows:
        key = str(getattr(row, "key", "") or "").strip()
        value = str(getattr(row, "value", "") or "").strip()
        if not key and not value:
            continue
        metadata = dict(getattr(row, "metadata", {}) or {})
        trust_level = classify_memory_trust_level(
            scope=str(getattr(row, "scope", "") or ""),
            metadata=metadata,
            timestamp=str(getattr(row, "updated_at", "") or getattr(row, "created_at", "") or ""),
        )
        if synthesis_disposition_for_trust_level(trust_level) == "exclude":
            continue
        rendered.append(f"- [{prefix}][trust={trust_level}] {key}: {value}")
    return rendered


def _evaluate_session_write(metadata: dict[str, Any]) -> MemoryWritePolicyDecision:
    kind = str(metadata.get("kind") or "").strip().lower() or "session_capture"
    trust_level: MemoryTrustLevel = "authoritative" if kind == "chat_input" else "advisory"
    metadata["write_threshold"] = "session_turn_capture"
    metadata["write_rationale"] = _resolve_rationale(metadata, _SESSION_RATIONALES.get(kind, "session_turn_capture"))
    metadata["trust_level"] = trust_level
    metadata["conflict_resolution"] = "none"
    return MemoryWritePolicyDecision(
        allow_write=True,
        metadata=metadata,
        conflict_resolution="none",
    )


def _evaluate_reference_write(metadata: dict[str, Any]) -> MemoryWritePolicyDecision:
    kind = str(metadata.get("kind") or metadata.get("type") or "").strip().lower()
    trust_level = str(metadata.get("trust_level") or "").strip().lower()
    if trust_level not in _ALLOWED_TRUST_LEVELS:
        trust_level = "advisory"
    metadata["write_threshold"] = "reference_context_capture"
    metadata["write_rationale"] = _resolve_rationale(metadata, _REFERENCE_RATIONALES.get(kind, "reference_context_capture"))
    metadata["trust_level"] = trust_level
    metadata["conflict_resolution"] = "none"
    return MemoryWritePolicyDecision(
        allow_write=True,
        metadata=metadata,
        conflict_resolution="none",
    )


def _evaluate_profile_write(
    *,
    key: str,
    value: str,
    metadata: dict[str, Any],
    existing_value: str,
    existing_metadata: dict[str, Any],
) -> MemoryWritePolicyDecision:
    threshold = _profile_write_threshold(key)
    metadata["write_threshold"] = threshold
    metadata["write_rationale"] = _resolve_rationale(metadata, _default_profile_rationale(threshold))
    metadata["trust_level"] = "authoritative"
    conflict_resolution: MemoryConflictResolution = "none"

    if existing_value and existing_value == value:
        conflict_resolution = "no_change"
    elif _is_older_observation(metadata, existing_metadata):
        conflict_resolution = "stale_update_rejected"
        return _rejected_profile_decision(
            metadata=metadata,
            conflict_resolution=conflict_resolution,
            error_code="E_PROFILE_MEMORY_STALE_UPDATE",
            error_message=f"Profile memory key '{key}' rejected a stale update.",
        )
    elif existing_value and existing_value != value and key.startswith("user_fact."):
        if not _is_truthy(metadata.get("user_correction")):
            conflict_resolution = "contradiction_requires_correction"
            return _rejected_profile_decision(
                metadata=metadata,
                conflict_resolution=conflict_resolution,
                error_code="E_PROFILE_MEMORY_CONTRADICTION_REQUIRES_CORRECTION",
                error_message=(
                    f"Profile memory key '{key}' requires metadata.user_correction=true to replace an existing fact."
                ),
            )
        conflict_resolution = "user_correction"
    elif existing_value and existing_value != value:
        conflict_resolution = "setting_update"

    if conflict_resolution not in _ALLOWED_CONFLICT_RESOLUTIONS:
        conflict_resolution = "none"
    metadata["conflict_resolution"] = conflict_resolution
    return MemoryWritePolicyDecision(
        allow_write=True,
        metadata=metadata,
        conflict_resolution=conflict_resolution,
    )


def _rejected_profile_decision(
    *,
    metadata: dict[str, Any],
    conflict_resolution: MemoryConflictResolution,
    error_code: str,
    error_message: str,
) -> MemoryWritePolicyDecision:
    metadata["conflict_resolution"] = conflict_resolution
    return MemoryWritePolicyDecision(
        allow_write=False,
        metadata=metadata,
        conflict_resolution=conflict_resolution,
        error_code=error_code,
        error_message=error_message,
    )


def _profile_write_threshold(key: str) -> str:
    if key.startswith("user_fact."):
        return "confirmed_user_fact"
    if key.startswith("user_preference."):
        return "explicit_preference_persist"
    return "profile_setting_persist"


def _default_profile_rationale(threshold: str) -> str:
    if threshold == "confirmed_user_fact":
        return "confirmed_user_fact_persist"
    if threshold == "explicit_preference_persist":
        return "explicit_user_preference_persist"
    return "profile_setting_persist"


def _resolve_rationale(metadata: Mapping[str, Any], default_value: str) -> str:
    rationale = str(metadata.get("write_rationale") or "").strip()
    return rationale or default_value


def _is_older_observation(metadata: Mapping[str, Any], existing_metadata: Mapping[str, Any]) -> bool:
    incoming = _parse_datetime(
        metadata.get("observed_at")
        or metadata.get("source_timestamp")
        or metadata.get("recorded_at")
        or metadata.get("timestamp")
    )
    existing = _parse_datetime(
        existing_metadata.get("observed_at")
        or existing_metadata.get("source_timestamp")
        or existing_metadata.get("recorded_at")
        or existing_metadata.get("timestamp")
    )
    return incoming is not None and existing is not None and incoming < existing


def _is_stale(metadata: Mapping[str, Any], *, fallback_timestamp: str) -> bool:
    stale_at = _parse_datetime(metadata.get("stale_at") or metadata.get("expires_at"))
    if stale_at is not None:
        return datetime.now(UTC) > stale_at
    explicit = str(metadata.get("trust_level") or "").strip().lower()
    if explicit == "stale_risk":
        return True
    refreshed_at = _parse_datetime(metadata.get("refreshed_at"))
    if refreshed_at is not None:
        return False
    timestamp_value = _parse_datetime(
        metadata.get("observed_at")
        or metadata.get("source_timestamp")
        or metadata.get("timestamp")
        or fallback_timestamp
    )
    max_age_minutes = metadata.get("max_age_minutes")
    if timestamp_value is None or max_age_minutes in {None, ""}:
        return False
    try:
        max_age = float(max_age_minutes)
    except (TypeError, ValueError):
        return False
    age_seconds = (datetime.now(UTC) - timestamp_value).total_seconds()
    return age_seconds > (max_age * 60.0)


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
