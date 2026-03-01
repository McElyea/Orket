from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from orket.capabilities.audio_player import build_audio_player
from orket.capabilities.tts_piper import PiperTTSProvider, build_tts_provider
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket_extension_sdk.audio import NullAudioPlayer, NullTTSProvider


def test_build_tts_provider_defaults_to_null() -> None:
    provider = build_tts_provider(input_config={})
    assert isinstance(provider, NullTTSProvider)


def test_build_tts_provider_uses_piper_when_configured(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"fake-model")
    fake_bin = tmp_path / "piper.exe"
    fake_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr("orket.capabilities.tts_piper.shutil.which", lambda _cmd: str(fake_bin))

    provider = build_tts_provider(
        input_config={
            "tts_backend": "piper",
            "tts_model_path": str(model),
            "tts_executable": str(fake_bin),
            "tts_sample_rate": 24000,
        }
    )
    assert isinstance(provider, PiperTTSProvider)

    def _fake_run(cmd, input, capture_output, check):  # noqa: ANN001
        del cmd, input, capture_output, check
        return SimpleNamespace(returncode=0, stdout=b"\x00\x00\x01\x00", stderr=b"")

    monkeypatch.setattr("orket.capabilities.tts_piper.subprocess.run", _fake_run)
    clip = provider.synthesize("hello there", voice_id="test_voice", emotion_hint="defensive", speed=1.0)
    assert clip.sample_rate == 24000
    assert clip.channels == 1
    assert clip.format == "pcm_s16le"
    assert clip.samples == b"\x00\x00\x01\x00"


def test_build_audio_player_defaults_to_null() -> None:
    player = build_audio_player(input_config={})
    assert isinstance(player, NullAudioPlayer)


def test_capability_registry_builder_registers_configured_piper_provider(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "voice.onnx"
    model.write_bytes(b"fake-model")
    fake_bin = tmp_path / "piper.exe"
    fake_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr("orket.capabilities.tts_piper.shutil.which", lambda _cmd: str(fake_bin))
    artifacts = WorkloadArtifacts(tmp_path, ReproducibilityEnforcer(tmp_path))
    registry = artifacts.build_sdk_capability_registry(
        workspace=tmp_path / "workspace",
        artifact_root=tmp_path / "artifacts",
        input_config={
            "tts_backend": "piper",
            "tts_model_path": str(model),
            "tts_executable": str(fake_bin),
        },
    )
    assert isinstance(registry.tts(), PiperTTSProvider)

