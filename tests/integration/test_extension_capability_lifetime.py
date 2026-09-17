"""Real executor effects with controlled delays, failures, and cancellation."""
from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

import pytest

from orket.application.services.extension_runtime_service import ExtensionRuntimeService
from orket_extension_sdk.audio import NullTTSProvider

CAPABILITIES = ["model_status", "stt_status", "transcribe", "tts_voices", "synthesize", "voice_control"]


class DelayedCall:
    def __init__(self, operation, marker, *, fail=False):
        self.operation, self.marker, self.fail = operation, marker, fail
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()

    def __call__(self, *args):
        self.entered.set()
        try:
            if not self.release.wait(5):
                raise TimeoutError("Test did not release the capability worker")
            self.marker.write_text("settled", encoding="utf-8")
            if self.fail:
                raise OSError("capability failed after its effect")
            return self.operation(*args)
        finally:
            self.finished.set()


async def delay_capability(service, capability, monkeypatch, marker, *, fail=False):
    if capability == "model_status":
        owner, name = service._model_provider, "is_available"
    elif capability in {"stt_status", "transcribe"}:
        owner, name = service._stt_provider, "transcribe"
    elif capability in {"tts_voices", "synthesize"}:
        if isinstance(service._tts_provider, NullTTSProvider):
            null = service._tts_provider
            service._tts_provider = SimpleNamespace(list_voices=null.list_voices, synthesize=null.synthesize)
        owner = service._tts_provider
        name = "list_voices" if capability == "tts_voices" else "synthesize"
    else:
        state = await service._extension_state("orket.test")
        owner, name = state.voice_controller, "control"
    delayed = DelayedCall(getattr(owner, name), marker, fail=fail)
    monkeypatch.setattr(owner, name, delayed)
    return delayed


async def invoke_capability(service, capability):
    if capability.endswith("status"):
        return await service.status(extension_id="orket.test")
    if capability == "transcribe":
        return await service.transcribe(extension_id="orket.test", audio_b64="aGVsbG8=", mime_type="audio/wav")
    if capability == "tts_voices":
        return await service.tts_voices(extension_id="orket.test")
    if capability == "synthesize":
        return await service.synthesize(extension_id="orket.test", text="hello")
    return await service.voice_control(extension_id="orket.test", command="start")


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", CAPABILITIES)
@pytest.mark.parametrize("mode", ["complete", "cancel", "cancel_failure", "timeout"])
# Layer: integration
async def test_capability_worker_settles_before_request_completion(tmp_path, monkeypatch, capability, mode):
    service = ExtensionRuntimeService(project_root=tmp_path, tts_provider=NullTTSProvider(),
                                      model_provider=SimpleNamespace(is_available=lambda: True))
    delayed = await delay_capability(service, capability, monkeypatch, tmp_path / "effect.txt",
                                     fail=mode == "cancel_failure")
    operation = invoke_capability(service, capability)
    task = asyncio.create_task(asyncio.wait_for(operation, 0.05) if mode == "timeout" else operation)
    try:
        assert await asyncio.to_thread(delayed.entered.wait, 5)
        if mode.startswith("cancel"):
            for _ in range(3):
                task.cancel()
                await asyncio.sleep(0)
        await asyncio.sleep(0.08 if mode == "timeout" else 0.03)
        assert not task.done(), "Request settled while its capability worker could still write"
        assert not delayed.finished.is_set() and not await asyncio.to_thread(delayed.marker.exists)
        delayed.release.set()
        if mode == "complete":
            result = await task
            assert result["extension_id"] == "orket.test"
            if capability == "voice_control":
                assert result["state"] == "listening"
        else:
            error = {"cancel": asyncio.CancelledError, "cancel_failure": OSError, "timeout": TimeoutError}[mode]
            with pytest.raises(error):
                await task
        assert delayed.finished.is_set()
        assert await asyncio.to_thread(delayed.marker.read_text, encoding="utf-8") == "settled"
    finally:
        delayed.release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert await asyncio.to_thread(delayed.finished.wait, 5)
        await service.close()
