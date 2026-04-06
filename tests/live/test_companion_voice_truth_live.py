from __future__ import annotations

import asyncio
import base64
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from orket.interfaces.api import create_api_app
from tests.live.test_runtime_stability_closeout_live import _live_enabled, _live_model

pytestmark = pytest.mark.end_to_end

_COMPANION_ROOT = Path(r"C:\source\orket-extensions\companion")
_COMPANION_SRC = _COMPANION_ROOT / "src"
_COMPANION_UI_ROOT = _COMPANION_ROOT / "UI"
_PIPER_MODEL_PATH = r"C:\Source\Orket\data\voices\en_US-lessac-medium.onnx"
_PIPER_VOICES_DIR = r"C:\Source\Orket\data\voices"
_PIPER_VOICE_ID = "en_US-lessac-medium"


def _build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enable_piper: bool) -> TestClient:
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    if enable_piper:
        monkeypatch.setenv("ORKET_TTS_BACKEND", "piper")
        monkeypatch.setenv("ORKET_TTS_PIPER_MODEL_PATH", _PIPER_MODEL_PATH)
        monkeypatch.setenv("ORKET_TTS_PIPER_VOICES_DIR", _PIPER_VOICES_DIR)
        monkeypatch.setenv("ORKET_TTS_PIPER_BIN", "piper")
    else:
        monkeypatch.setenv("ORKET_TTS_BACKEND", "null")
    return TestClient(create_api_app(project_root=tmp_path))


def _headers() -> dict[str, str]:
    return {"X-API-Key": "test-key"}


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _gateway_app():
    sys.path.insert(0, str(_COMPANION_SRC))
    from companion_app.server import app as gateway_app

    return gateway_app


def _wait_for_http_ready(url: str, *, timeout_seconds: float) -> None:
    started = time.perf_counter()
    while time.perf_counter() - started < timeout_seconds:
        try:
            import httpx

            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except Exception:
            time.sleep(0.2)
            continue
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {url}")


async def _run_command(*args: str, cwd: Path) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


def test_companion_voice_truth_live_tts_generation_is_explicit(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. Verifies the real companion API exposes available TTS truth with actual audio bytes."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live companion voice proof.")

    client = _build_client(tmp_path, monkeypatch, enable_piper=True)
    headers = _headers()

    status = client.get("/v1/extensions/orket.companion/runtime/status", headers=headers)
    voices = client.get("/v1/extensions/orket.companion/runtime/tts/voices", headers=headers)
    synth = client.post(
        "/v1/extensions/orket.companion/runtime/tts/synthesize",
        headers=headers,
        json={"text": "hello world", "voice_id": _PIPER_VOICE_ID},
    )

    assert status.status_code == 200
    assert voices.status_code == 200
    assert synth.status_code == 200

    status_payload = status.json()
    voices_payload = voices.json()
    synth_payload = synth.json()
    audio_bytes = base64.b64decode(synth_payload["audio_b64"].encode("utf-8"), validate=True)

    print(
        "[live][companion][voice-truth][tts-available] "
        f"path=primary result=success "
        f"tts_available={status_payload['tts_available']} "
        f"voice_id={synth_payload['voice_id']} "
        f"audio_bytes={len(audio_bytes)}"
    )
    assert status_payload["ok"] is True
    assert status_payload["tts_available"] is True
    assert voices_payload["ok"] is True
    assert voices_payload["tts_available"] is True
    assert _PIPER_VOICE_ID in {row["voice_id"] for row in voices_payload["voices"]}
    assert synth_payload["ok"] is True
    assert synth_payload["voice_id"] == _PIPER_VOICE_ID
    assert synth_payload["sample_rate"] == 22050
    assert synth_payload["channels"] == 1
    assert synth_payload["format"] == "pcm_s16le"
    assert len(audio_bytes) > 0
    assert synth_payload["error_code"] is None
    assert synth_payload["error_message"] == ""


def test_companion_voice_truth_live_text_generation_remains_distinct_from_tts(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. Verifies real provider-backed text generation remains distinct from the TTS surface."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live companion voice proof.")

    client = _build_client(tmp_path, monkeypatch, enable_piper=True)
    headers = _headers()
    session_id = "voice-truth-live"

    generate = client.post(
        "/v1/extensions/orket.companion/runtime/llm/generate",
        headers=headers,
        json={
            "system_prompt": "Reply with OK exactly once.",
            "user_message": "Reply with OK exactly once.",
            "provider": "ollama",
            "model": _live_model(),
        },
    )
    synth = client.post(
        "/v1/extensions/orket.companion/runtime/tts/synthesize",
        headers=headers,
        json={"text": "OK", "voice_id": _PIPER_VOICE_ID},
    )

    assert generate.status_code == 200
    assert synth.status_code == 200

    generate_payload = generate.json()
    synth_payload = synth.json()
    audio_bytes = base64.b64decode(synth_payload["audio_b64"].encode("utf-8"), validate=True)

    print(
        "[live][companion][voice-truth][text-vs-tts] "
        f"path=primary result=success session_id={session_id} model={generate_payload['model']} "
        f"tts_voice={synth_payload['voice_id']} audio_bytes={len(audio_bytes)}"
    )
    assert generate_payload["ok"] is True
    assert str(generate_payload["text"]).strip()
    assert "audio_b64" not in generate_payload
    assert synth_payload["ok"] is True
    assert synth_payload["voice_id"] == _PIPER_VOICE_ID
    assert len(audio_bytes) > 0
    assert synth_payload["error_code"] is None


@pytest.mark.asyncio
async def test_companion_voice_truth_live_gateway_playback_without_avatar(tmp_path: Path, monkeypatch) -> None:
    """Layer: end-to-end. Verifies gateway/UI playback truth works with avatar mode disabled and no lipsync dependency."""
    if not _live_enabled():
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live companion playback proof.")
    if not await asyncio.to_thread(_COMPANION_ROOT.exists):
        pytest.skip("Companion extension checkout is required for gateway playback proof.")
    if not await asyncio.to_thread((_COMPANION_UI_ROOT / "node_modules" / "playwright").exists):
        pytest.skip("Companion UI Playwright dependency is required for gateway playback proof.")

    host_port = _reserve_port()
    gateway_port = _reserve_port()
    base_url = f"http://127.0.0.1:{gateway_port}"
    output_path = tmp_path / "gateway_playback_probe.json"

    monkeypatch.setenv("ORKET_API_KEY", "core-key")
    monkeypatch.setenv("COMPANION_HOST_BASE_URL", f"http://127.0.0.1:{host_port}")
    monkeypatch.setenv("COMPANION_API_KEY", "core-key")
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORKET_TTS_BACKEND", "piper")
    monkeypatch.setenv("ORKET_TTS_PIPER_MODEL_PATH", _PIPER_MODEL_PATH)
    monkeypatch.setenv("ORKET_TTS_PIPER_VOICES_DIR", _PIPER_VOICES_DIR)
    monkeypatch.setenv("ORKET_TTS_PIPER_BIN", "piper")

    host_app = create_api_app(project_root=tmp_path / "host_workspace")
    gateway_app = _gateway_app()
    host_server = uvicorn.Server(
        uvicorn.Config(host_app, host="127.0.0.1", port=host_port, log_level="critical", access_log=False),
    )
    gateway_server = uvicorn.Server(
        uvicorn.Config(gateway_app, host="127.0.0.1", port=gateway_port, log_level="critical", access_log=False),
    )
    host_thread = threading.Thread(target=host_server.run, daemon=True)
    gateway_thread = threading.Thread(target=gateway_server.run, daemon=True)

    host_thread.start()
    gateway_thread.start()

    try:
        _wait_for_http_ready(f"http://127.0.0.1:{host_port}/health", timeout_seconds=20.0)
        _wait_for_http_ready(f"{base_url}/healthz", timeout_seconds=20.0)

        exit_code, stdout, stderr = await _run_command(
            "node",
            "scripts/live_ui_interrupt_probe.mjs",
            "--base-url",
            base_url,
            "--message",
            "phase c playback truth probe",
            "--timeout-sec",
            "90",
            "--raf-sample-sec",
            "1",
            "--speaking-raf-sample-sec",
            "2",
            "--avatar-mode",
            "off",
            "--provider",
            "ollama",
            "--model",
            _live_model(),
            "--output",
            str(output_path),
            cwd=_COMPANION_UI_ROOT,
        )
        if exit_code != 0:
            raise AssertionError(
                "gateway playback probe failed "
                f"(exit_code={exit_code}, stdout={stdout.strip()}, stderr={stderr.strip()})"
            )

        probe_payload = json.loads(output_path.read_bytes().decode("utf-8"))
        checks = dict(probe_payload.get("checks") or {})
        request_counts = dict(probe_payload.get("request_counts") or {})

        print(
            "[live][companion][voice-truth][gateway-playback] "
            f"path=primary result=success avatar_mode={probe_payload.get('avatar_mode')} "
            f"chat_requests={request_counts.get('chat')} "
            f"voice_synth_requests={request_counts.get('voiceSynthesize')} "
            f"stop_playback={checks.get('stop_playback_cleared')}"
        )
        assert probe_payload["ok"] is True
        assert probe_payload["avatar_mode"] == "off"
        assert checks["synced_notice"] is True
        assert checks["chat_request"] is True
        assert checks["speak_button_enabled"] is True
        assert checks["speak_started"] is True
        assert checks["stop_playback_observed"] is True
        assert checks["stop_playback_cleared"] is True
        assert int(request_counts.get("chat", 0) or 0) >= 1
        assert int(request_counts.get("voiceSynthesize", 0) or 0) >= 1
    finally:
        gateway_server.should_exit = True
        host_server.should_exit = True
        gateway_thread.join(timeout=6)
        host_thread.join(timeout=6)
