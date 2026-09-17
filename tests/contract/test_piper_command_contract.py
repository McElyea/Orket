"""Controlled native-owner results prove translation and fail-closed selection, not inference."""
from __future__ import annotations

import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.capabilities.tts_piper import PiperConfig, PiperSynthesisError, PiperTTSProvider, build_tts_provider
from orket.core.contracts.owned_command import CommandExecutionUncertain, OwnedCommandResult
from orket_extension_sdk.audio import AudioClip, NullTTSProvider, VoiceInfo

BASE = OwnedCommandResult(0, b"\x00\x00", b"", "completed", True, True, "controlled", 1, 2, 3, ())


class ResultRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self.result


@pytest.fixture
def piper_model(tmp_path):
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"controlled-model")
    model.with_suffix(".onnx.json").write_text('{"audio":{"sample_rate":22050}}', encoding="utf-8")
    return model


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"reason": "timeout", "returncode": None}, {"returncode": 7},
    {"reason": "output_limit", "capture_complete": False},
    {"reason": "capture_incomplete", "capture_complete": False},
    {"reason": "cleanup_unconfirmed", "cleanup_confirmed": False},
])
# Layer: contract
async def test_piper_cannot_return_pcm_from_a_failed_native_observation(piper_model, changes):
    result = replace(BASE, **changes)
    runner = ResultRunner(result)
    provider = PiperTTSProvider(PiperConfig(piper_model, executable=sys.executable),
                               command_runner=runner, workspace=piper_model.parent)
    error = CommandExecutionUncertain if not result.cleanup_confirmed else PiperSynthesisError
    with pytest.raises(error) as observed:
        await provider.synthesize_async("hello", "voice")
    assert observed.value.lifetime is result
    assert runner.calls[0][1]["input_data"] == b"hello"


@pytest.mark.parametrize("config,code", [
    ({"tts_backend": "missing"}, "E_TTS_BACKEND_UNSUPPORTED"),
    ({"tts_backend": "piper"}, "E_PIPER_MODEL_REQUIRED"),
    ({"tts_backend": "piper", "tts_model_path": "voice.onnx"}, "E_PIPER_COMMAND_OWNER_REQUIRED"),
])
# Layer: contract
def test_explicit_tts_selection_does_not_silently_become_null(config, code):
    with pytest.raises(ValueError, match=code):
        build_tts_provider(input_config=config)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
# Layer: contract
def test_piper_requires_a_finite_positive_deadline(piper_model, timeout):
    with pytest.raises(ValueError, match="E_PIPER_TIMEOUT_INVALID"):
        PiperConfig(piper_model, timeout_seconds=timeout)


# Layer: contract
def test_missing_explicit_executable_has_no_available_voice_catalog(piper_model):
    runner = ResultRunner(BASE)
    provider = build_tts_provider(command_runner=runner, workspace=piper_model.parent,
        input_config={"tts_backend": "piper", "tts_model_path": str(piper_model),
                      "tts_executable": str(piper_model.parent / "missing-piper")})
    assert isinstance(provider, PiperTTSProvider) and provider.list_voices() == []
    assert runner.calls == [], "Construction and discovery must not spawn probe processes"


# Layer: contract
def test_quoted_executable_path_preserves_its_arguments(piper_model):
    command = f'"{sys.executable}" "-m" "piper"'
    assert PiperTTSProvider._resolve_executable(command) == [sys.executable, "-m", "piper"]


@pytest.mark.asyncio
# Layer: contract
async def test_embedding_piper_subclass_keeps_its_synchronous_implementation(piper_model):
    class BorrowedPiper(PiperTTSProvider):
        def synthesize(self, text, voice_id, emotion_hint="neutral", speed=1.0):
            return AudioClip(sample_rate=22050, channels=1, samples=b"\x02\x00\x03\x00")

    runner = ResultRunner(BASE)
    provider = BorrowedPiper(PiperConfig(piper_model, executable=sys.executable),
                            command_runner=runner, workspace=piper_model.parent)
    service = ExtensionRuntimeService(project_root=piper_model.parent, tts_provider=provider,
                                       model_provider=SimpleNamespace(is_available=lambda: True))
    response = await service.synthesize(extension_id="orket.test", text="hello")
    assert response["audio_b64"] == "AgADAA==" and response["process_lifetime"] is None
    assert runner.calls == [], "The host bypassed the embedding's synchronous override"
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("samples", [b"\x02\x00", b""])
# Layer: contract
async def test_null_subclass_with_its_own_voice_is_not_classified_as_builtin_null(tmp_path, samples):
    class BorrowedTTS(NullTTSProvider):
        def list_voices(self):
            return [VoiceInfo(voice_id="borrowed", display_name="Borrowed", language="und")]

        def synthesize(self, *args):
            return AudioClip(sample_rate=22050, channels=1, samples=samples)

    service = ExtensionRuntimeService(project_root=tmp_path, tts_provider=BorrowedTTS(),
                                       model_provider=SimpleNamespace(is_available=lambda: True))
    voices = await service.tts_voices(extension_id="orket.test")
    assert voices["tts_available"] and voices["default_voice_id"] == "borrowed"
    response = await service.synthesize(extension_id="orket.test", text="hello")
    assert response["ok"] is bool(samples)
    assert response["error_code"] == (None if samples else "tts_empty_audio")
    await service.close()
