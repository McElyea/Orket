from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_SAME_ORIGIN_HEADERS = {"origin": "http://testserver"}


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
        assert '<div id="root"></div>' in home.text
        assert "/static/app.js" in home.text
        assert client.get("/healthz").json() == {"ok": True}
        app_js = client.get("/static/app.js")
        assert app_js.status_code == 200
        assert '"/chat"' in app_js.text
        assert '"/config"' in app_js.text
        assert '"/voice/control"' in app_js.text
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
            headers=_SAME_ORIGIN_HEADERS,
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
            headers=_SAME_ORIGIN_HEADERS,
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


def test_external_extension_template_server_proxies_chat_and_config(monkeypatch) -> None:
    """Layer: integration. Verifies template chat/config routes proxy to the host API client seam."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            def __init__(self) -> None:
                self.last_get_config_session_id = ""
                self.last_update_config: dict[str, object] = {}
                self.last_chat: dict[str, object] = {}

            async def get_config(self, *, session_id: str) -> dict[str, object]:
                self.last_get_config_session_id = session_id
                return {
                    "ok": True,
                    "session_id": session_id,
                    "config": {
                        "mode": {"role_id": "general_assistant", "relationship_style": "platonic"},
                        "memory": {
                            "session_memory_enabled": True,
                            "profile_memory_enabled": True,
                            "episodic_memory_enabled": False,
                        },
                        "voice": {
                            "enabled": False,
                            "silence_delay_sec": 1.5,
                            "silence_delay_min_sec": 0.2,
                            "silence_delay_max_sec": 10.0,
                            "adaptive_cadence_enabled": False,
                            "adaptive_cadence_min_sec": 0.4,
                            "adaptive_cadence_max_sec": 4.0,
                        },
                    },
                }

            async def update_config(self, *, session_id: str, scope: str, patch: dict[str, object]) -> dict[str, object]:
                self.last_update_config = {"session_id": session_id, "scope": scope, "patch": patch}
                return {"ok": True, "session_id": session_id, "scope": scope, "config": patch}

            async def chat(
                self,
                *,
                session_id: str,
                message: str,
                provider: str = "",
                model: str = "",
            ) -> dict[str, object]:
                self.last_chat = {
                    "session_id": session_id,
                    "message": message,
                    "provider": provider,
                    "model": model,
                }
                return {
                    "ok": True,
                    "session_id": session_id,
                    "turn_id": "turn.000001",
                    "message": "hello from fake host seam",
                    "model": model or "fake-model",
                    "latency_ms": 7,
                    "text_only_degraded": False,
                }

        fake_client = _FakeClient()
        monkeypatch.setattr(server_module, "_client", lambda: fake_client)
        client = TestClient(server_module.app)

        config_response = client.get("/api/config", params={"session_id": "s-test"})
        assert config_response.status_code == 200
        assert config_response.json()["ok"] is True
        assert fake_client.last_get_config_session_id == "s-test"

        config_patch = {
            "mode": {"role_id": "researcher", "relationship_style": "platonic"},
            "memory": {
                "session_memory_enabled": True,
                "profile_memory_enabled": False,
                "episodic_memory_enabled": False,
            },
            "voice": {"silence_delay_sec": 2.1},
        }
        update_response = client.patch(
            "/api/config",
            headers=_SAME_ORIGIN_HEADERS,
            json={"session_id": "s-test", "scope": "next_turn", "patch": config_patch},
        )
        assert update_response.status_code == 200
        assert update_response.json()["scope"] == "next_turn"
        assert fake_client.last_update_config == {
            "session_id": "s-test",
            "scope": "next_turn",
            "patch": config_patch,
        }

        chat_response = client.post(
            "/api/chat",
            headers=_SAME_ORIGIN_HEADERS,
            json={
                "session_id": "s-test",
                "message": "Can you summarize this?",
                "provider": "ollama",
                "model": "qwen2.5-coder:7b",
            },
        )
        assert chat_response.status_code == 200
        assert chat_response.json()["message"] == "hello from fake host seam"
        assert fake_client.last_chat == {
            "session_id": "s-test",
            "message": "Can you summarize this?",
            "provider": "ollama",
            "model": "qwen2.5-coder:7b",
        }
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_requires_companion_api_key(monkeypatch) -> None:
    """Layer: contract. Verifies gateway fails closed when COMPANION_API_KEY is missing."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        monkeypatch.delenv("COMPANION_API_KEY", raising=False)
        import companion_app.server as server_module

        client = TestClient(server_module.app)
        response = client.get("/api/status")
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_GATEWAY_API_KEY_REQUIRED"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_blocks_cross_origin_mutations(monkeypatch) -> None:
    """Layer: contract. Verifies mutating routes are rejected when request Origin does not match gateway origin."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            async def chat(self, *, session_id: str, message: str, provider: str = "", model: str = "") -> dict[str, object]:
                return {
                    "ok": True,
                    "session_id": session_id,
                    "turn_id": "turn.1",
                    "message": message,
                    "model": model or "fake-model",
                    "latency_ms": 1,
                    "text_only_degraded": False,
                }

        monkeypatch.setattr(server_module, "_client", lambda: _FakeClient())
        client = TestClient(server_module.app)
        response = client.post(
            "/api/chat",
            headers={"origin": "http://evil.test"},
            json={"session_id": "session-1", "message": "hello"},
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_GATEWAY_CSRF_BLOCKED"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_enforces_loopback_clients(monkeypatch) -> None:
    """Layer: contract. Verifies gateway rejects non-loopback clients when loopback enforcement is enabled."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        monkeypatch.setattr(server_module, "_LOOPBACK_HOSTS", frozenset({"127.0.0.1", "::1", "localhost"}))
        client = TestClient(server_module.app)
        response = client.get("/api/status")
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_GATEWAY_LOOPBACK_REQUIRED"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_rejects_oversized_config_patch(monkeypatch) -> None:
    """Layer: contract. Verifies oversized config patches are rejected before host client execution."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            async def update_config(self, *, session_id: str, scope: str, patch: dict[str, object]) -> dict[str, object]:
                raise AssertionError("host client should not be called for oversized patch")

        monkeypatch.setattr(server_module, "_MAX_CONFIG_PATCH_BYTES", 32)
        monkeypatch.setattr(server_module, "_client", lambda: _FakeClient())
        client = TestClient(server_module.app)
        response = client.patch(
            "/api/config",
            headers=_SAME_ORIGIN_HEADERS,
            json={
                "session_id": "session-1",
                "scope": "next_turn",
                "patch": {"mode": {"role_id": "x" * 128}},
            },
        )
        assert response.status_code == 413
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_CONFIG_PATCH_TOO_LARGE"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_rejects_oversized_chat_message(monkeypatch) -> None:
    """Layer: contract. Verifies oversized chat payloads are rejected before host client execution."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            async def chat(
                self,
                *,
                session_id: str,
                message: str,
                provider: str = "",
                model: str = "",
            ) -> dict[str, object]:
                raise AssertionError("host client should not be called for oversized chat message")

        monkeypatch.setattr(server_module, "_MAX_CHAT_MESSAGE_BYTES", 12)
        monkeypatch.setattr(server_module, "_client", lambda: _FakeClient())
        client = TestClient(server_module.app)
        response = client.post(
            "/api/chat",
            headers=_SAME_ORIGIN_HEADERS,
            json={"session_id": "session-1", "message": "message that is too large"},
        )
        assert response.status_code == 413
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_CHAT_MESSAGE_TOO_LARGE"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)


def test_external_extension_template_server_rejects_oversized_audio_payload(monkeypatch) -> None:
    """Layer: contract. Verifies oversized audio payloads are rejected before host STT execution."""
    repo_root = Path(__file__).resolve().parents[2]
    template_root = repo_root / "docs" / "templates" / "external_extension"
    src_root = template_root / "src"
    sys.path.insert(0, str(src_root))
    try:
        import companion_app.server as server_module

        class _FakeClient:
            async def voice_transcribe(
                self,
                *,
                audio_b64: str,
                mime_type: str = "audio/wav",
                language_hint: str = "",
            ) -> dict[str, object]:
                raise AssertionError("host client should not be called for oversized audio payload")

        monkeypatch.setattr(server_module, "_MAX_AUDIO_B64_BYTES", 16)
        monkeypatch.setattr(server_module, "_client", lambda: _FakeClient())
        client = TestClient(server_module.app)
        response = client.post(
            "/api/voice/transcribe",
            headers=_SAME_ORIGIN_HEADERS,
            json={"audio_b64": "A" * 40, "mime_type": "audio/wav", "language_hint": "en"},
        )
        assert response.status_code == 413
        detail = response.json()["detail"]
        assert detail["ok"] is False
        assert detail["code"] == "E_COMPANION_AUDIO_PAYLOAD_TOO_LARGE"
    finally:
        sys.path = [entry for entry in sys.path if entry != str(src_root)]
        for module_name in list(sys.modules):
            if module_name == "companion_app" or module_name.startswith("companion_app."):
                sys.modules.pop(module_name, None)
            if module_name == "companion_extension" or module_name.startswith("companion_extension."):
                sys.modules.pop(module_name, None)
