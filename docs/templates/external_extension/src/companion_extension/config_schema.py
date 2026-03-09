from __future__ import annotations

from pydantic import BaseModel, Field


class MemoryConfig(BaseModel):
    session_memory_enabled: bool = True
    profile_memory_enabled: bool = True


class VoiceConfig(BaseModel):
    enabled: bool = False
    silence_delay_seconds: float = Field(default=1.5, ge=0.2, le=6.0)


class CompanionDefaults(BaseModel):
    mode: str = Field(min_length=1)
    style: str = Field(min_length=1)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
