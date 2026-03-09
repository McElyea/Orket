from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

VoiceTurnState = Literal["idle", "listening", "processing"]
VoiceTurnCommand = Literal["start", "stop", "submit"]


@dataclass(frozen=True)
class TranscribeRequest:
    audio_bytes: bytes
    mime_type: str = "audio/wav"
    language_hint: str = ""


@dataclass(frozen=True)
class TranscribeResponse:
    ok: bool
    text: str = ""
    error_code: str | None = None
    error_message: str = ""


@dataclass(frozen=True)
class VoiceTurnControlRequest:
    command: VoiceTurnCommand
    silence_delay_seconds: float | None = None


@dataclass(frozen=True)
class VoiceTurnControlResponse:
    ok: bool
    state: VoiceTurnState
    error_code: str | None = None
    error_message: str = ""


@runtime_checkable
class STTProvider(Protocol):
    def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        ...


@runtime_checkable
class VoiceTurnController(Protocol):
    def control(self, request: VoiceTurnControlRequest) -> VoiceTurnControlResponse:
        ...

    def state(self) -> VoiceTurnState:
        ...


class NullSTTProvider:
    def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        del request
        return TranscribeResponse(
            ok=False,
            text="",
            error_code="stt_unavailable",
            error_message="No STT provider configured.",
        )


class NullVoiceTurnController:
    def control(self, request: VoiceTurnControlRequest) -> VoiceTurnControlResponse:
        del request
        return VoiceTurnControlResponse(
            ok=False,
            state="idle",
            error_code="voice_unavailable",
            error_message="No voice turn controller configured.",
        )

    def state(self) -> VoiceTurnState:
        return "idle"
