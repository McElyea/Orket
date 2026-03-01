from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AudioClip:
    sample_rate: int
    channels: int
    samples: bytes
    format: str = "pcm_s16le"


@dataclass(frozen=True)
class VoiceInfo:
    voice_id: str
    display_name: str
    language: str
    tags: list[str] = field(default_factory=list)


@runtime_checkable
class TTSProvider(Protocol):
    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        ...

    def list_voices(self) -> list[VoiceInfo]:
        ...


@runtime_checkable
class AudioPlayer(Protocol):
    def play(self, clip: AudioClip, blocking: bool = False) -> None:
        ...

    def stop(self) -> None:
        ...


class NullTTSProvider:
    """Deterministic, silent fallback for environments without TTS backend."""

    def synthesize(
        self,
        text: str,
        voice_id: str,
        emotion_hint: str = "neutral",
        speed: float = 1.0,
    ) -> AudioClip:
        del text, voice_id, emotion_hint, speed
        return AudioClip(sample_rate=22050, channels=1, samples=b"", format="pcm_s16le")

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(voice_id="null", display_name="Null Voice", language="und", tags=["silent", "fallback"])]


class NullAudioPlayer:
    """No-op playback for CI/headless execution."""

    def play(self, clip: AudioClip, blocking: bool = False) -> None:
        del clip, blocking

    def stop(self) -> None:
        return

