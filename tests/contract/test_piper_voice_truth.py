"""Actual asset files and API service translation with controlled native-command results."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket.capabilities.tts_piper import PiperConfig, PiperTTSProvider
from tests.contract.test_piper_command_contract import BASE, ResultRunner


def voice_file(root, name, sample_rate=22050):
    model = root / f"{name}.onnx"
    model.write_bytes(b"controlled-model")
    model.with_suffix(".onnx.json").write_text(json.dumps({"audio": {"sample_rate": sample_rate}}), encoding="utf-8")
    return model


@pytest.fixture
def voices(tmp_path):
    default = voice_file(tmp_path, "z_default", 22050)
    other = voice_file(tmp_path, "a_other", 24000)
    return default, other


def service_for(model, *, runner=None, **config):
    owner = runner or ResultRunner(BASE)
    provider = PiperTTSProvider(PiperConfig(model, executable=sys.executable, **config),
                               command_runner=owner, workspace=model.parent)
    service = ExtensionRuntimeService(project_root=model.parent, tts_provider=provider,
                                      model_provider=SimpleNamespace(is_available=lambda: True))
    return service, owner


@pytest.mark.asyncio
@pytest.mark.parametrize("requested,expected,rate", [("", "z_default", 22050), ("A_OTHER", "a_other", 24000)])
# Layer: contract
async def test_api_reports_the_selected_canonical_voice_and_model_sample_rate(voices, requested, expected, rate):
    default, _other = voices
    service, owner = service_for(default)
    catalog = await service.tts_voices(extension_id="orket.test")
    assert catalog["default_voice_id"] == "z_default"
    response = await service.synthesize(extension_id="orket.test", text="hello", voice_id=requested)
    assert response["voice_id"] == expected and response["sample_rate"] == rate
    assert Path(owner.calls[0][0][owner.calls[0][0].index("--model") + 1]).stem == expected
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_unknown_voice_refuses_before_native_admission(voices):
    service, owner = service_for(voices[0])
    with pytest.raises(ValueError, match="E_PIPER_VOICE_UNKNOWN"):
        await service.synthesize(extension_id="orket.test", text="hello", voice_id="missing")
    assert owner.calls == []
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_explicit_rate_expectation_cannot_relabel_the_model_audio(voices):
    service, owner = service_for(voices[0], sample_rate=48000)
    with pytest.raises(ValueError, match="E_PIPER_SAMPLE_RATE_MISMATCH"):
        await service.synthesize(extension_id="orket.test", text="hello", voice_id="z_default")
    assert owner.calls == []
    await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, [], {}, {"audio": None}, {"audio": {"sample_rate": True}},
                                    {"audio": {"sample_rate": 0}}, {"audio": {"sample_rate": "24000"}},
                                    {"audio": {"sample_rate": 24000.5}}])
# Layer: contract
async def test_invalid_model_metadata_cannot_become_successful_audio(voices, metadata):
    default = voices[0]
    await asyncio.to_thread(default.with_suffix(".onnx.json").write_text, json.dumps(metadata), encoding="utf-8")
    service, owner = service_for(default)
    with pytest.raises(ValueError, match="E_PIPER_MODEL_METADATA_INVALID"):
        await service.synthesize(extension_id="orket.test", text="hello", voice_id="z_default")
    assert owner.calls == []
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_missing_default_cannot_silently_select_another_catalog_voice(voices):
    default, _other = voices
    await asyncio.to_thread(default.unlink)
    service, owner = service_for(default)
    with pytest.raises(ValueError, match="E_PIPER_DEFAULT_MODEL_UNAVAILABLE"):
        await service.synthesize(extension_id="orket.test", text="hello")
    assert owner.calls == []
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_casefold_voice_collision_cannot_select_by_discovery_order(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(second.mkdir)
    default = await asyncio.to_thread(voice_file, first, "Voice")
    await asyncio.to_thread(voice_file, second, "voice")
    service, owner = service_for(default, voices_dir=second)
    with pytest.raises(ValueError, match="E_PIPER_VOICE_AMBIGUOUS"):
        await service.synthesize(extension_id="orket.test", text="hello", voice_id="voice")
    assert owner.calls == []
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_native_config_snapshot_and_response_metadata_use_the_same_bytes(voices):
    default = voices[0]
    metadata_path = default.with_suffix(".onnx.json")
    original = await asyncio.to_thread(metadata_path.read_bytes)
    snapshots = []

    class InspectingRunner(ResultRunner):
        async def run(self, argv, **kwargs):
            await asyncio.to_thread(metadata_path.write_text, '{"audio":{"sample_rate":48000}}', encoding="utf-8")
            snapshot = Path(argv[argv.index("--config") + 1])
            snapshots.append(snapshot)
            assert await asyncio.to_thread(snapshot.read_bytes) == original
            return await super().run(argv, **kwargs)

    service, _owner = service_for(default, runner=InspectingRunner(BASE))
    response = await service.synthesize(extension_id="orket.test", text="hello", voice_id="z_default")
    assert response["sample_rate"] == 22050
    assert response["voice_metadata"]["model_config_sha256"] == hashlib.sha256(original).hexdigest()
    assert response["voice_metadata"]["voice_id"] == response["voice_id"] == "z_default"
    assert snapshots and not await asyncio.to_thread(snapshots[0].parent.exists)
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_equivalent_model_paths_do_not_create_a_false_voice_collision(tmp_path):
    await asyncio.to_thread((tmp_path / "nested").mkdir)
    await asyncio.to_thread(voice_file, tmp_path, "voice")
    model = tmp_path / "nested" / ".." / "voice.onnx"
    service, owner = service_for(model, voices_dir=tmp_path)
    response = await service.synthesize(extension_id="orket.test", text="hello", voice_id="voice")
    assert response["voice_id"] == "voice" and len(owner.calls) == 1
    await service.close()


@pytest.mark.asyncio
# Layer: contract
async def test_relative_asset_paths_are_bound_to_the_owner_workspace(tmp_path):
    await asyncio.to_thread(voice_file, tmp_path, "voice", 24000)
    owner = ResultRunner(BASE)
    provider = PiperTTSProvider(PiperConfig(Path("voice.onnx"), executable=sys.executable),
                               command_runner=owner, workspace=tmp_path)
    result = await provider.synthesize_async("hello", "voice")
    assert result.voice.model_path == tmp_path / "voice.onnx"
    assert result.clip.sample_rate == 24000 and len(owner.calls) == 1
