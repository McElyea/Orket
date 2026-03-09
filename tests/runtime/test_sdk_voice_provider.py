from __future__ import annotations

from orket.capabilities.sdk_voice_provider import HostSTTCapabilityProvider, HostVoiceTurnController
from orket_extension_sdk.voice import TranscribeRequest, TranscribeResponse, VoiceTurnControlRequest


def test_host_voice_turn_controller_transition_happy_path() -> None:
    """Layer: integration. Verifies start/submit/stop transitions for host-owned voice turn control."""
    controller = HostVoiceTurnController()
    started = controller.control(VoiceTurnControlRequest(command="start"))
    assert started.ok is True
    assert started.state == "listening"
    assert controller.state() == "listening"

    submitted = controller.control(VoiceTurnControlRequest(command="submit"))
    assert submitted.ok is True
    assert submitted.state == "processing"
    assert controller.state() == "idle"

    stopped = controller.control(VoiceTurnControlRequest(command="stop"))
    assert stopped.ok is True
    assert stopped.state == "idle"


def test_host_voice_turn_controller_invalid_transition_fails_closed() -> None:
    """Layer: integration. Verifies invalid transitions return explicit errors without mutating state."""
    controller = HostVoiceTurnController()
    invalid_submit = controller.control(VoiceTurnControlRequest(command="submit"))
    assert invalid_submit.ok is False
    assert invalid_submit.error_code == "voice_invalid_transition"
    assert controller.state() == "idle"

    assert controller.control(VoiceTurnControlRequest(command="start")).ok is True
    duplicate_start = controller.control(VoiceTurnControlRequest(command="start"))
    assert duplicate_start.ok is False
    assert duplicate_start.error_code == "voice_invalid_transition"
    assert controller.state() == "listening"


def test_host_voice_turn_controller_clamps_silence_delay() -> None:
    """Layer: integration. Verifies silence-delay updates are clamped to host-configured min/max bounds."""
    controller = HostVoiceTurnController(
        default_silence_delay_seconds=2.0,
        min_silence_delay_seconds=0.5,
        max_silence_delay_seconds=4.0,
    )
    controller.control(VoiceTurnControlRequest(command="stop", silence_delay_seconds=99.0))
    assert controller.silence_delay_seconds() == 4.0
    controller.control(VoiceTurnControlRequest(command="stop", silence_delay_seconds=0.1))
    assert controller.silence_delay_seconds() == 0.5


def test_host_stt_provider_default_and_custom_transcriber() -> None:
    """Layer: integration. Verifies STT provider reports unavailable by default and uses host transcriber when configured."""
    unavailable = HostSTTCapabilityProvider()
    unavailable_result = unavailable.transcribe(TranscribeRequest(audio_bytes=b"pcm"))
    assert unavailable_result.ok is False
    assert unavailable_result.error_code == "stt_unavailable"

    provider = HostSTTCapabilityProvider(
        transcriber=lambda request: TranscribeResponse(ok=True, text=f"bytes={len(request.audio_bytes)}")
    )
    result = provider.transcribe(TranscribeRequest(audio_bytes=b"abcdef"))
    assert result.ok is True
    assert result.text == "bytes=6"
