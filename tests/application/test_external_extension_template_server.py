from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_external_extension_template_server_serves_static_ui() -> None:
    """Layer: contract. Verifies external extension template web server boots and serves static UI assets."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        from companion_app.server import app

        client = TestClient(app)
        home = client.get("/")
        assert home.status_code == 200
        assert "Companion MVP Template" in home.text
        assert "Synthesize Audio" in home.text
        assert "avatar-face" in home.text
        assert client.get("/healthz").json() == {"ok": True}
        app_js = client.get("/static/app.js")
        assert app_js.status_code == 200
        assert "/api/voice/synthesize" in app_js.text
        assert "/api/voice/voices" in app_js.text
        assert "/api/voice/cadence/suggest" in app_js.text
        assert "updateAvatarExpression" in app_js.text
        assert client.get("/static/styles.css").status_code == 200
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_proxies_voice_synthesize(monkeypatch) -> None:
    """Layer: integration. Verifies template voice synthesize route proxies to the host API client seam."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            async def voice_voices(self) -> dict[str, object]:
                return {
                    "ok": True,
                    "tts_available": True,
                    "default_voice_id": "demo_voice",
                    "voices": [
                        {
                            "voice_id": "demo_voice",
                            "display_name": "Demo Voice",
                            "language": "en",
                            "tags": ["test"],
                        }
                    ],
                }

            async def voice_synthesize(
                self,
                *,
                text: str,
                voice_id: str = "",
                emotion_hint: str = "neutral",
                speed: float = 1.0,
            ) -> dict[str, object]:
                return {
                    "ok": bool(text),
                    "voice_id": voice_id or "test_voice",
                    "emotion_hint": emotion_hint,
                    "speed": speed,
                    "sample_rate": 22050,
                    "channels": 1,
                    "format": "pcm_s16le",
                    "audio_b64": "AQI=",
                    "error_code": None,
                    "error_message": "",
                }

            async def voice_cadence_suggest(self, *, session_id: str, text: str) -> dict[str, object]:
                return {
                    "ok": True,
                    "session_id": session_id,
                    "adaptive_cadence_enabled": True,
                    "source": "adaptive",
                    "suggested_silence_delay_sec": 1.4,
                    "input_words": len(text.split()),
                }

        monkeypatch.setattr(server_module, "_client", lambda: _FakeClient())
        client = TestClient(server_module.app)
        response = client.post(
            "/api/voice/synthesize",
            json={"text": "Hello synth", "voice_id": "demo_voice", "emotion_hint": "calm", "speed": 1.2},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert payload["voice_id"] == "demo_voice"
        assert payload["audio_b64"] == "AQI="
        voices = client.get("/api/voice/voices")
        assert voices.status_code == 200
        voices_payload = voices.json()
        assert voices_payload["ok"] is True
        assert voices_payload["voices"][0]["voice_id"] == "demo_voice"
        cadence = client.post(
            "/api/voice/cadence/suggest",
            json={"session_id": "demo-session", "text": "hello cadence route"},
        )
        assert cadence.status_code == 200
        cadence_payload = cadence.json()
        assert cadence_payload["source"] == "adaptive"
        assert cadence_payload["suggested_silence_delay_sec"] == 1.4
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)
