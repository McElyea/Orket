"""TCP shutdown owns capability threads; speech responses are controlled in these tests."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext

import pytest

from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_extension_capability_lifetime import CAPABILITIES, delay_capability
from tests.integration.test_extension_generation_api_lifetime import generation_app as generation_app


def capability_route(capability):
    if capability.endswith("status"):
        return "GET", "status", None
    if capability == "transcribe":
        return "POST", "voice/transcribe", {"audio_b64": "aGVsbG8=", "mime_type": "audio/wav"}
    if capability == "tts_voices":
        return "GET", "tts/voices", None
    if capability == "synthesize":
        return "POST", "tts/synthesize", {"text": "hello"}
    return "POST", "voice/control", {"command": "start"}


@pytest.mark.asyncio
@pytest.mark.parametrize("capability", CAPABILITIES)
@pytest.mark.parametrize("fail", [False, True])
# Layer: integration
async def test_tcp_shutdown_retains_capability_effect_and_failure(generation_app, monkeypatch, tmp_path, capability, fail):
    context = generation_app.state.api_runtime_context
    service = context.extension_runtime_service
    delayed = await delay_capability(service, capability, monkeypatch, tmp_path / "tcp-effect.txt", fail=fail)
    method, route, body = capability_route(capability)
    request, closing = None, None
    retained_failure = None
    # The shared TCP fixture closes again on exit; a failed owner must repeat its failure.
    expected_exit = pytest.raises(RuntimeError, match="teardown failed") if fail else nullcontext()
    with expected_exit as exit_failure:
        async with serving_api(generation_app) as client:
            try:
                request = asyncio.create_task(client.request(method, f"/v1/extensions/orket.test/runtime/{route}", json=body))
                assert await asyncio.to_thread(delayed.entered.wait, 5)
                closing = asyncio.create_task(context.close())
                for _ in range(3):
                    await asyncio.sleep(0)
                    closing.cancel()
                await asyncio.sleep(0.03)
                assert not closing.done() and not context.closed and context.active_request_count == 1
                assert not delayed.finished.is_set() and not service._model_provider._provider.client.is_closed
                assert (await client.get("/health")).status_code == 503
                delayed.release.set()
                with pytest.raises(RuntimeError if fail else asyncio.CancelledError) as observed:
                    await closing
                retained_failure = observed.value if fail else None
                if fail:
                    assert isinstance(retained_failure.__cause__, OSError)
                assert (await request).status_code == (500 if fail else 503)
                assert context.closed is (not fail) and context.active_request_count == 0
                assert delayed.finished.is_set() and service._model_provider._provider.client.is_closed
                assert await asyncio.to_thread(delayed.marker.read_text, encoding="utf-8") == "settled"
            finally:
                delayed.release.set()
                await asyncio.gather(*(task for task in (request, closing) if task is not None), return_exceptions=True)
    if fail:
        assert exit_failure.value is retained_failure
