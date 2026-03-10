from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from orket.capabilities.sdk_llm_provider import LocalModelCapabilityProvider
from orket.services.scoped_memory_store import ScopedMemoryRecord
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse

from .companion_config_models import CompanionConfig


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_system_prompt(*, config: CompanionConfig, memory_context: str, history_context: str) -> str:
    mode = config.mode
    role_guidance = _role_prompt_guidance(mode.role_id.value)
    relationship_guidance = _relationship_style_guidance(mode.relationship_style.value)
    sections = [
        "You are Companion running on Orket host runtime authority.",
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
        "girlfriend": "Role guidance: supportive, affectionate girlfriend-style companion persona for consenting adults.",
        "husband": "Role guidance: steady, caring husband-style companion persona for consenting adults.",
        "general_assistant": "Role guidance: balanced companion; helpful, clear, and emotionally steady.",
        "supportive_listener": (
            "Role guidance: prioritize empathy, validation, and reflective listening before problem-solving."
        ),
        "strategist": "Role guidance: structure responses into practical steps, options, and tradeoffs.",
        "tutor": "Role guidance: teach patiently with simple explanations, examples, and gentle checks for understanding.",
        "researcher": "Role guidance: be exploratory and curious; ask clarifying questions and surface useful context.",
        "programmer": "Role guidance: be technical and precise; favor actionable implementation details.",
    }
    return guidance_map.get(role, "")


def _relationship_style_guidance(style_id: str) -> str:
    style = str(style_id or "").strip().lower()
    guidance_map = {
        "platonic": (
            "Relationship guidance: friendly, emotionally available, non-romantic companion tone."
        ),
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


def generate_with_provider_overrides(
    request: GenerateRequest,
    provider_override: str,
    model_override: str,
) -> GenerateResponse:
    model = model_override or "qwen2.5-coder:7b"
    provider = provider_override.strip()
    previous_llm_provider = os.environ.get("ORKET_LLM_PROVIDER")
    previous_model_provider = os.environ.get("ORKET_MODEL_PROVIDER")
    try:
        if provider:
            os.environ["ORKET_LLM_PROVIDER"] = provider
            os.environ["ORKET_MODEL_PROVIDER"] = provider
        provider_client = LocalModelCapabilityProvider(model=model, temperature=0.2, seed=None)
        return provider_client.generate(request)
    finally:
        if previous_llm_provider is None:
            os.environ.pop("ORKET_LLM_PROVIDER", None)
        else:
            os.environ["ORKET_LLM_PROVIDER"] = previous_llm_provider
        if previous_model_provider is None:
            os.environ.pop("ORKET_MODEL_PROVIDER", None)
        else:
            os.environ["ORKET_MODEL_PROVIDER"] = previous_model_provider
