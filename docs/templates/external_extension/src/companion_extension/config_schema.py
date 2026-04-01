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


class ModeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_id: CompanionRoleId = CompanionRoleId.GENERAL_ASSISTANT
    relationship_style: RelationshipStyleId = RelationshipStyleId.PLATONIC
    custom_style: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_custom_style(self) -> ModeConfig:
        if self.relationship_style == RelationshipStyleId.CUSTOM and not self.custom_style:
            raise ValueError("custom_style required when relationship_style is custom")
        if self.relationship_style != RelationshipStyleId.CUSTOM and self.custom_style is not None:
            raise ValueError("custom_style is only allowed when relationship_style is custom")
        return self


class MemoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True
    episodic_memory_enabled: bool = False


class VoiceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    silence_delay_sec: float = Field(default=1.5, ge=0.0)
    silence_delay_min_sec: float = Field(default=0.2, ge=0.0)
    silence_delay_max_sec: float = Field(default=6.0, gt=0.0)
    adaptive_cadence_enabled: bool = False
    adaptive_cadence_min_sec: float = Field(default=0.4, ge=0.0)
    adaptive_cadence_max_sec: float = Field(default=4.0, gt=0.0)

    @model_validator(mode="after")
    def _clamp_silence_delay(self) -> VoiceConfig:
        if self.silence_delay_max_sec < self.silence_delay_min_sec:
            raise ValueError("silence_delay_max_sec must be >= silence_delay_min_sec")
        if self.adaptive_cadence_max_sec < self.adaptive_cadence_min_sec:
            raise ValueError("adaptive_cadence_max_sec must be >= adaptive_cadence_min_sec")
        clamped = max(self.silence_delay_min_sec, min(self.silence_delay_max_sec, self.silence_delay_sec))
        clamped_adaptive_min = max(
            self.silence_delay_min_sec,
            min(self.silence_delay_max_sec, self.adaptive_cadence_min_sec),
        )
        clamped_adaptive_max = max(
            clamped_adaptive_min,
            min(self.silence_delay_max_sec, self.adaptive_cadence_max_sec),
        )
        self.silence_delay_sec = clamped
        self.adaptive_cadence_min_sec = clamped_adaptive_min
        self.adaptive_cadence_max_sec = clamped_adaptive_max
        return self


class CompanionDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: ModeConfig = Field(default_factory=ModeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
