from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompanionRoleId(str, Enum):
    NONE = "none"
    WAIFU = "waifu"
    BOYFRIEND = "boyfriend"
    GIRLFRIEND = "girlfriend"
    HUSBAND = "husband"
    ROLE_PLAY = "role_play"
    RESEARCHER = "researcher"
    PROGRAMMER = "programmer"
    STRATEGIST = "strategist"
    TUTOR = "tutor"
    SUPPORTIVE_LISTENER = "supportive_listener"
    GENERAL_ASSISTANT = "general_assistant"


class RelationshipStyleId(str, Enum):
    PLATONIC = "platonic"
    ROMANTIC = "romantic"
    INTERMEDIATE = "intermediate"
    CUSTOM = "custom"


BLOCKED_MODE_COMBINATIONS: frozenset[tuple[CompanionRoleId, RelationshipStyleId]] = frozenset()


def validate_mode_combination(role_id: CompanionRoleId, relationship_style: RelationshipStyleId) -> None:
    if (role_id, relationship_style) in BLOCKED_MODE_COMBINATIONS:
        raise ValueError(
            f"E_COMPANION_MODE_COMBINATION_BLOCKED: role={role_id.value};relationship_style={relationship_style.value}"
        )


class CompanionModeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: CompanionRoleId = CompanionRoleId.GENERAL_ASSISTANT
    relationship_style: RelationshipStyleId = RelationshipStyleId.PLATONIC
    custom_style: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_custom_style_rules(self) -> CompanionModeConfig:
        is_custom_style = self.relationship_style == RelationshipStyleId.CUSTOM
        has_custom_style = bool(self.custom_style)
        if is_custom_style and not has_custom_style:
            raise ValueError("E_COMPANION_CUSTOM_STYLE_REQUIRED")
        if not is_custom_style and self.custom_style is not None:
            raise ValueError("E_COMPANION_CUSTOM_STYLE_FORBIDDEN")
        validate_mode_combination(self.role_id, self.relationship_style)
        return self


class CompanionMemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True
    episodic_memory_enabled: bool = False


class CompanionVoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    silence_delay_sec: float = Field(default=2.0, ge=0.0)
    silence_delay_min_sec: float = Field(default=0.2, ge=0.0)
    silence_delay_max_sec: float = Field(default=10.0, gt=0.0)
    adaptive_cadence_enabled: bool = False
    adaptive_cadence_min_sec: float = Field(default=0.4, ge=0.0)
    adaptive_cadence_max_sec: float = Field(default=4.0, gt=0.0)

    @model_validator(mode="after")
    def _normalize_silence_delay(self) -> CompanionVoiceConfig:
        if self.silence_delay_max_sec < self.silence_delay_min_sec:
            raise ValueError("E_COMPANION_VOICE_BOUNDS_INVALID")
        if self.adaptive_cadence_max_sec < self.adaptive_cadence_min_sec:
            raise ValueError("E_COMPANION_ADAPTIVE_BOUNDS_INVALID")
        clamped_delay = max(self.silence_delay_min_sec, min(self.silence_delay_max_sec, self.silence_delay_sec))
        clamped_adaptive_min = max(
            self.silence_delay_min_sec,
            min(self.silence_delay_max_sec, self.adaptive_cadence_min_sec),
        )
        clamped_adaptive_max = max(
            clamped_adaptive_min,
            min(self.silence_delay_max_sec, self.adaptive_cadence_max_sec),
        )
        self.silence_delay_sec = clamped_delay
        self.adaptive_cadence_min_sec = clamped_adaptive_min
        self.adaptive_cadence_max_sec = clamped_adaptive_max
        return self


class CompanionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: CompanionModeConfig = Field(default_factory=CompanionModeConfig)
    memory: CompanionMemoryConfig = Field(default_factory=CompanionMemoryConfig)
    voice: CompanionVoiceConfig = Field(default_factory=CompanionVoiceConfig)
