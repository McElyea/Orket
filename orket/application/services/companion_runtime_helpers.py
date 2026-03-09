from __future__ import annotations

import json
from datetime import UTC, datetime

from orket.services.scoped_memory_store import ScopedMemoryRecord

from .companion_config_models import CompanionConfig


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_system_prompt(*, config: CompanionConfig, memory_context: str, history_context: str) -> str:
    mode = config.mode
    sections = [
        "You are Companion running on Orket host runtime authority.",
        f"Role: {mode.role_id.value}",
        f"Relationship style: {mode.relationship_style.value}",
    ]
    if mode.custom_style:
        sections.append("Custom style settings:\n" + json.dumps(mode.custom_style, sort_keys=True))
    if memory_context.strip():
        sections.append("Retrieved memory context:\n" + memory_context)
    if history_context.strip():
        sections.append("Recent conversation context:\n" + history_context)
    return "\n\n".join(sections)


def format_memory_rows(rows: list[ScopedMemoryRecord], *, prefix: str) -> list[str]:
    formatted: list[str] = []
    for row in rows:
        key = str(row.key or "").strip()
        value = str(row.value or "").strip()
        if not key and not value:
            continue
        formatted.append(f"- [{prefix}] {key}: {value}")
    return formatted


def format_history_context(history_rows: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for row in history_rows:
        role = str(row.get("role") or "").strip()
        content = str(row.get("content") or "").strip()
        if role and content:
            parts.append(f"{role}: {content}")
    return "\n".join(parts)
