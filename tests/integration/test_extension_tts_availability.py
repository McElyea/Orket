"""Actual TCP responses distinguish a silent null backend from speech availability."""
from __future__ import annotations

import pytest

from tests.integration.test_api_active_request_ownership import serving_api
from tests.integration.test_extension_generation_api_lifetime import generation_app as generation_app


@pytest.mark.asyncio
# Layer: integration
async def test_null_tts_status_catalog_and_synthesis_agree(generation_app):
    async with serving_api(generation_app) as client:
        prefix = "/v1/extensions/orket.test/runtime/"
        status = await client.get(prefix + "status")
        voices = await client.get(prefix + "tts/voices")
        synth = await client.post(prefix + "tts/synthesize", json={"text": "hello"})
        assert status.status_code == voices.status_code == synth.status_code == 200
        assert status.json()["tts_available"] is False
        assert voices.json()["tts_available"] is False and voices.json()["voices"] == []
        assert voices.json()["default_voice_id"] == ""
        assert synth.json()["ok"] is False and synth.json()["error_code"] == "tts_unavailable"
        assert synth.json()["audio_b64"] == "" and synth.json()["process_lifetime"] is None
    context = generation_app.state.api_runtime_context
    assert context.closed and context.active_request_count == 0
