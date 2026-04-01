from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .config_schema import CompanionDefaults


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_system_prompt(*, config: CompanionDefaults, memory_context: str, history_context: str) -> str:
    mode = config.mode
    role_guidance = _role_prompt_guidance(mode.role_id.value)
    relationship_guidance = _relationship_style_guidance(mode.relationship_style.value)
    sections = [
        "You are Companion.",
        "Active mode below is behavioral instruction and must guide response style for this turn.",
        f"Role: {mode.role_id.value}",
        f"Relationship style: {mode.relationship_style.value}",
    ]
    if role_guidance:
        sections.append(role_guidance)
    if relationship_guidance:
        sections.append(relationship_guidance)
    if mode.custom_style:
        sections.append("Custom style settings:\n" + json.dumps(mode.custom_style, sort_keys=True))
    if memory_context.strip():
        sections.append("Retrieved memory context:\n" + memory_context)
    if history_context.strip():
        sections.append("Recent conversation context:\n" + history_context)
    return "\n\n".join(sections)


def format_memory_rows(rows: list[dict[str, Any]], *, prefix: str) -> list[str]:
    rendered: list[str] = []
    for row in rows:
        key = str(row.get("key") or "").strip()
        value = str(row.get("value") or "").strip()
        if not key and not value:
            continue
        metadata = dict(row.get("metadata") or {})
        trust_level = classify_memory_trust_level(
            scope=str(row.get("scope") or ""),
            metadata=metadata,
            timestamp=str(row.get("updated_at") or row.get("created_at") or ""),
        )
        if synthesis_disposition_for_trust_level(trust_level) == "exclude":
            continue
        rendered.append(f"- [{prefix}][trust={trust_level}] {key}: {value}")
    return rendered


def format_history_context(history_rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in history_rows:
        role = str(row.get("role") or "").strip()
        content = str(row.get("content") or "").strip()
        if role and content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)


def suggest_adaptive_silence_delay(
    *,
    text: str,
    silence_delay_min_sec: float,
    silence_delay_max_sec: float,
    adaptive_cadence_min_sec: float,
    adaptive_cadence_max_sec: float,
) -> tuple[float, int]:
    words = max(1, len([part for part in str(text or "").split() if part.strip()]))
    ratio = min(1.0, words / 40.0)
    adaptive_target = adaptive_cadence_min_sec + ((adaptive_cadence_max_sec - adaptive_cadence_min_sec) * ratio)
    clamped = max(silence_delay_min_sec, min(silence_delay_max_sec, adaptive_target))
    return round(clamped, 2), words


def classify_memory_trust_level(*, scope: str, metadata: dict[str, Any], timestamp: str = "") -> str:
    if _is_stale(metadata, fallback_timestamp=timestamp):
        return "stale_risk"
    explicit = str(metadata.get("trust_level") or "").strip().lower()
    if explicit in {"authoritative", "advisory", "unverified"}:
        return explicit
    normalized_scope = str(scope or "").strip().lower()
    kind = str(metadata.get("kind") or metadata.get("type") or "").strip().lower()
    if normalized_scope == "profile_memory":
        return "authoritative"
    if normalized_scope == "session_memory":
        return "authoritative" if kind == "chat_input" else "advisory"
    if normalized_scope == "episodic_memory":
        return "advisory"
    return "unverified"


def synthesis_disposition_for_trust_level(trust_level: str) -> str:
    return "include" if str(trust_level or "").strip().lower() in {"authoritative", "advisory"} else "exclude"


def _role_prompt_guidance(role_id: str) -> str:
    role = str(role_id or "").strip().lower()
    guidance_map = {
        "none": "Role guidance: no preset role constraints; adapt naturally to the user's tone and requests.",
        "role_play": (
            "Role guidance: prioritize imaginative role-play when the user opts in, keep scene continuity, and "
            "separate role-play framing from real-world claims."
        ),
        "waifu": "Role guidance: warm, affectionate, emotionally available companion persona for consenting adults.",
        "boyfriend": "Role guidance: supportive, affectionate boyfriend-style companion persona for consenting adults.",
        "girlfriend": (
            "Role guidance: supportive, affectionate girlfriend-style companion persona for consenting adults."
        ),
        "husband": "Role guidance: steady, caring husband-style companion persona for consenting adults.",
        "general_assistant": "Role guidance: balanced companion; helpful, clear, and emotionally steady.",
        "supportive_listener": (
            "Role guidance: prioritize empathy, validation, and reflective listening before problem-solving."
        ),
        "strategist": "Role guidance: structure responses into practical steps, options, and tradeoffs.",
        "tutor": (
            "Role guidance: teach patiently with simple explanations, examples, and gentle checks for understanding."
        ),
        "researcher": "Role guidance: be exploratory and curious; ask clarifying questions and surface useful context.",
        "programmer": "Role guidance: be technical and precise; favor actionable implementation details.",
    }
    return guidance_map.get(role, "")


def _relationship_style_guidance(style_id: str) -> str:
    style = str(style_id or "").strip().lower()
    guidance_map = {
        "platonic": "Relationship guidance: friendly, emotionally available, non-romantic companion tone.",
        "intermediate": (
            "Relationship guidance: closer and more personal than platonic while remaining respectful and grounded."
        ),
        "romantic": (
            "Relationship guidance: warm, affectionate, and emotionally present for consenting adults. "
            "Do not silently downgrade to platonic tone. If refusal is required, keep tone caring and explicit."
        ),
        "custom": "Relationship guidance: follow custom style values as the highest presentation preference.",
    }
    return guidance_map.get(style, "")


def _is_stale(metadata: dict[str, Any], *, fallback_timestamp: str) -> bool:
    stale_at = _parse_datetime(metadata.get("stale_at"))
    if stale_at is not None:
        return stale_at <= datetime.now(UTC)
    expires_at = _parse_datetime(metadata.get("expires_at"))
    if expires_at is not None:
        return expires_at <= datetime.now(UTC)
    trust_level = str(metadata.get("trust_level") or "").strip().lower()
    if trust_level == "stale_risk":
        return True
    _ = _parse_datetime(metadata.get("observed_at") or fallback_timestamp)
    return False


def _parse_datetime(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
