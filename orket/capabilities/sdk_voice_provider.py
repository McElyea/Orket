from __future__ import annotations

from threading import RLock
from typing import Callable

from orket_extension_sdk.voice import (
    STTProvider,
    TranscribeRequest,
    TranscribeResponse,
    VoiceTurnCommand,
    VoiceTurnControlRequest,
    VoiceTurnControlResponse,
    VoiceTurnController,
    VoiceTurnState,
)


class HostSTTCapabilityProvider(STTProvider):
    def __init__(self, transcriber: Callable[[TranscribeRequest], TranscribeResponse] | None = None) -> None:
        self._transcriber = transcriber

    def transcribe(self, request: TranscribeRequest) -> TranscribeResponse:
        if self._transcriber is None:
            return TranscribeResponse(
                ok=False,
                text="",
                error_code="stt_unavailable",
                error_message="No STT provider configured.",
            )
        return self._transcriber(request)


class HostVoiceTurnController(VoiceTurnController):
    def __init__(
        self,
        *,
        default_silence_delay_seconds: float = 2.0,
        min_silence_delay_seconds: float = 0.2,
        max_silence_delay_seconds: float = 10.0,
    ) -> None:
        min_delay = max(0.0, float(min_silence_delay_seconds))
        max_delay = max(min_delay, float(max_silence_delay_seconds))
        self._min_silence_delay_seconds = min_delay
        self._max_silence_delay_seconds = max_delay
        self._silence_delay_seconds = self._clamp_delay(float(default_silence_delay_seconds))
        self._state: VoiceTurnState = "idle"
        self._lock = RLock()

    def control(self, request: VoiceTurnControlRequest) -> VoiceTurnControlResponse:
        with self._lock:
            if request.silence_delay_seconds is not None:
                self._silence_delay_seconds = self._clamp_delay(float(request.silence_delay_seconds))
            command = request.command
            if command == "start":
                return self._handle_start()
            if command == "stop":
                self._state = "idle"
                return VoiceTurnControlResponse(ok=True, state="idle")
            if command == "submit":
                return self._handle_submit()
            return VoiceTurnControlResponse(
                ok=False,
                state=self._state,
                error_code="voice_invalid_command",
                error_message=f"Unsupported voice command '{command}'.",
            )

    def state(self) -> VoiceTurnState:
        with self._lock:
            return self._state

    def silence_delay_seconds(self) -> float:
        with self._lock:
            return self._silence_delay_seconds

    def _handle_start(self) -> VoiceTurnControlResponse:
        if self._state == "idle":
            self._state = "listening"
            return VoiceTurnControlResponse(ok=True, state=self._state)
        return self._invalid_transition("start")

    def _handle_submit(self) -> VoiceTurnControlResponse:
        if self._state != "listening":
            return self._invalid_transition("submit")
        self._state = "processing"
        response = VoiceTurnControlResponse(ok=True, state="processing")
        self._state = "idle"
        return response

    def _invalid_transition(self, command: VoiceTurnCommand) -> VoiceTurnControlResponse:
        return VoiceTurnControlResponse(
            ok=False,
            state=self._state,
            error_code="voice_invalid_transition",
            error_message=f"Cannot apply command '{command}' from state '{self._state}'.",
        )

    def _clamp_delay(self, value: float) -> float:
        return max(self._min_silence_delay_seconds, min(self._max_silence_delay_seconds, float(value)))
