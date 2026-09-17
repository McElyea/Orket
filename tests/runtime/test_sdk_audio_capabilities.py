from __future__ import annotations

import json
from pathlib import Path

from orket.capabilities.audio_player import build_audio_player
from orket.capabilities.tts_piper import PiperTTSProvider, build_tts_provider
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.extensions.reproducibility import ReproducibilityEnforcer
from orket.extensions.workload_artifacts import WorkloadArtifacts
from orket_extension_sdk.audio import NullAudioPlayer, NullTTSProvider


class RecordingRunner:
    def __init__(self):
        self.calls = []

    async def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return OwnedCommandResult(0, b"\x00\x00\x01\x00", b"", "completed", True, True,
                                  "controlled", 1, 2, 3, ())


def write_model(path, sample_rate=22050):
    path.write_bytes(b"controlled-model")
    path.with_suffix(".onnx.json").write_text(json.dumps({"audio": {"sample_rate": sample_rate}}), encoding="utf-8")


# Layer: contract
def test_build_tts_provider_defaults_to_null() -> None:
    provider = build_tts_provider(input_config={})
    assert isinstance(provider, NullTTSProvider)


# Layer: contract
def test_build_tts_provider_uses_piper_when_configured(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "voice.onnx"
    write_model(model, 24000)
    fake_bin = tmp_path / "piper.exe"
    fake_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr("orket.capabilities.tts_piper.shutil.which", lambda _cmd: str(fake_bin))

    runner = RecordingRunner()
    provider = build_tts_provider(workspace=tmp_path, command_runner=runner,
        input_config={
            "tts_backend": "piper",
            "tts_model_path": str(model),
            "tts_executable": str(fake_bin),
            "tts_sample_rate": 24000,
        }
    )
    assert isinstance(provider, PiperTTSProvider)

    clip = provider.synthesize("hello there", voice_id="voice", emotion_hint="defensive", speed=1.0)
    assert clip.sample_rate == 24000
    assert clip.channels == 1
    assert clip.format == "pcm_s16le"
    assert clip.samples == b"\x00\x00\x01\x00"
    assert runner.calls[0][1]["input_data"] == b"hello there"
    assert runner.calls[0][1]["output_limit_bytes"] == 64 * 1024 * 1024


# Layer: contract
def test_piper_provider_lists_and_resolves_multiple_voice_models(tmp_path: Path, monkeypatch) -> None:
    default_model = tmp_path / "voice_default.onnx"
    write_model(default_model)
    secondary_model = tmp_path / "voice_alt.onnx"
    write_model(secondary_model)
    fake_bin = tmp_path / "piper.exe"
    fake_bin.write_text("", encoding="utf-8")
    monkeypatch.setattr("orket.capabilities.tts_piper.shutil.which", lambda _cmd: str(fake_bin))

    runner = RecordingRunner()
    provider = build_tts_provider(workspace=tmp_path, command_runner=runner,
        input_config={
            "tts_backend": "piper",
            "tts_model_path": str(default_model),
            "tts_voices_dir": str(tmp_path),
            "tts_executable": str(fake_bin),
            "tts_sample_rate": 22050,
        }
    )
    assert isinstance(provider, PiperTTSProvider)
    voices = provider.list_voices()
    assert [voice.voice_id for voice in voices] == ["voice_default", "voice_alt"]

    provider.synthesize("hello there", voice_id="voice_alt")
    cmd = runner.calls[0][0]
    assert isinstance(cmd, list)
    model_index = cmd.index("--model")
    assert str(cmd[model_index + 1]).endswith("voice_alt.onnx")


# Layer: contract
def test_build_audio_player_defaults_to_null() -> None:
    player = build_audio_player(input_config={})
    assert isinstance(player, NullAudioPlayer)


# Layer: contract
def test_capability_registry_builder_registers_configured_piper_provider(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "voice.onnx"
    write_model(model)
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


# Layer: contract
def test_build_tts_provider_falls_back_to_python_module_piper_when_path_shim_missing(tmp_path: Path, monkeypatch) -> None:
    model = tmp_path / "voice.onnx"
    write_model(model)
    monkeypatch.setattr("orket.capabilities.tts_piper.shutil.which", lambda _cmd: None)

    monkeypatch.setattr("orket.capabilities.tts_piper.sys.executable", "python")
    monkeypatch.setattr("orket.capabilities.tts_piper.importlib.util.find_spec", lambda name: object())

    runner = RecordingRunner()
    provider = build_tts_provider(workspace=tmp_path, command_runner=runner,
        input_config={
            "tts_backend": "piper",
            "tts_model_path": str(model),
            "tts_executable": "piper",
            "tts_sample_rate": 22050,
        }
    )
    assert isinstance(provider, PiperTTSProvider)
    clip = provider.synthesize("hello", voice_id="voice")
    assert clip.samples == b"\x00\x00\x01\x00"
    assert runner.calls[0][0][:3] == ["python", "-m", "piper"]
    assert len(runner.calls) == 1, "Executable discovery must not launch a help probe"
