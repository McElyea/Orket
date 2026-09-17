"""Real command trees through the builtin Piper adapter and authenticated TCP API."""
from __future__ import annotations

import asyncio
import subprocess
import sys

import pytest

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.capabilities.tts_piper import PiperConfig, PiperSynthesisError, PiperTTSProvider
from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_extension_generation_api_lifetime import generation_app as generation_app
from tests.integration.test_verification_process_lifetime import WORKER, assert_stopped, await_tree, stop_observed


def tree_provider(root, mode):
    model = root / "voice.onnx"
    model.write_bytes(b"controlled-model")
    model.with_suffix(".onnx.json").write_text('{"audio":{"sample_rate":22050}}', encoding="utf-8")
    command = subprocess.list2cmdline([sys.executable, str(WORKER), str(root), "2", "detached", "ignore-term", mode])
    return PiperTTSProvider(PiperConfig(model, executable=command, timeout_seconds=5 if mode == "timeout" else 15),
                            command_runner=CommandProcessSupervisor(root, cancellation_event="piper_process_cancelled"),
                            workspace=root)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["cancel", "repeated-cancel", "timeout", "leader-exit", "leader-failure"])
# Layer: integration
async def test_piper_owns_detached_resistant_children_and_grandchildren(tmp_path, mode, caplog):
    provider = await asyncio.to_thread(tree_provider, tmp_path, mode)
    task = asyncio.create_task(provider.synthesize_async("hello", "voice"))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if "cancel" in mode:
            task.cancel()
            if mode == "repeated-cancel":
                for _ in range(3):
                    await asyncio.sleep(0)
                    task.cancel()
            with pytest.raises(CommandProcessCancelled) as observed:
                await asyncio.wait_for(task, 5)
            result = observed.value.lifetime
            events = [r.orket_record["data"] for r in caplog.records if r.message == "piper_process_cancelled"]
            assert len(events) == 1 and all(events[0].get(key) == value for key, value in result.lifetime().items())
        else:
            if mode.startswith("leader"):
                await asyncio.to_thread((tmp_path / "release-leader").touch)
            if mode == "leader-exit":
                synthesis = await asyncio.wait_for(task, 5)
                result = synthesis.command
                assert synthesis.clip.samples == b"" and result.returncode == 0
            else:
                with pytest.raises(PiperSynthesisError) as observed:
                    await asyncio.wait_for(task, 10)
                result = observed.value.lifetime
                assert result.reason == ("timeout" if mode == "timeout" else "completed")
                if mode == "leader-failure":
                    assert result.returncode == 7
        assert result.cleanup_confirmed and result.backend in {"windows_job", "linux_subreaper"}
        await assert_stopped(processes, tmp_path)
        assert not await asyncio.to_thread(lambda: list(tmp_path.glob(".orket-piper-*")))
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.to_thread(stop_observed, processes)


@pytest.mark.asyncio
# Layer: integration
async def test_tcp_piper_shutdown_stops_the_active_native_tree(generation_app, tmp_path, caplog):
    context = generation_app.state.api_runtime_context
    context.extension_runtime_service._tts_provider = await asyncio.to_thread(tree_provider, tmp_path, "cancel")
    processes, request, closing = [], None, None
    async with serving_api(generation_app) as client:
        try:
            request = asyncio.create_task(client.post("/v1/extensions/orket.test/runtime/tts/synthesize",
                                                      json={"text": "hello", "voice_id": "voice"}))
            processes = await await_tree(tmp_path)
            closing = asyncio.create_task(context.close())
            for _ in range(3):
                await asyncio.sleep(0)
                closing.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(closing, 5)
            assert (await request).status_code == 503
            assert context.closed and context.active_request_count == context.active_background_task_count == 0
            assert context.extension_runtime_service._model_provider._provider.client.is_closed
            await assert_stopped(processes, tmp_path)
            events = [r.orket_record["data"] for r in caplog.records if r.message == "piper_process_cancelled"]
            assert len(events) == 1 and events[0]["cleanup_confirmed"] and events[0]["reason"] == "cancelled"
        finally:
            await asyncio.to_thread(stop_observed, processes)
            await asyncio.gather(*(task for task in (request, closing) if task is not None), return_exceptions=True)
