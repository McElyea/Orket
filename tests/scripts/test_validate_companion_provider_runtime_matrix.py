from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts.companion.run_companion_provider_runtime_matrix import run_companion_provider_runtime_matrix
from scripts.companion.validate_companion_provider_runtime_matrix import main


def _validator_transport() -> httpx.MockTransport:
    memory_tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/companion/status":
            return httpx.Response(200, json={"ok": True, "stt_available": True})
        if request.url.path == "/api/v1/companion/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/v1/companion/voice/control":
            payload = json.loads(request.content.decode("utf-8"))
            state = {"start": "listening", "stop": "idle", "submit": "processing"}.get(str(payload.get("command") or ""), "idle")
            return httpx.Response(200, json={"ok": True, "state": state})
        if request.url.path == "/api/v1/companion/chat":
            payload = json.loads(request.content.decode("utf-8"))
            session_id = str(payload.get("session_id") or "")
            message = str(payload.get("message") or "")
            model = str(payload.get("model") or "")
            if "17 * 19" in message:
                return httpx.Response(200, json={"message": "323", "latency_ms": 500, "model": model})
            if "MODE_OK" in message:
                return httpx.Response(200, json={"message": "Tutor: MODE_OK", "latency_ms": 620, "model": model})
            if "feel overwhelmed" in message:
                return httpx.Response(200, json={"message": "I understand. Try one practical step.", "latency_ms": 750, "model": model})
            if "Remember this for later" in message:
                token = message.split("favorite_color=", 1)[-1].split(".", 1)[0].strip()
                memory_tokens[session_id] = token
                return httpx.Response(200, json={"message": "stored", "latency_ms": 490, "model": model})
            if "What favorite_color" in message:
                token = memory_tokens.get(session_id, "missing")
                return httpx.Response(200, json={"message": f"favorite_color={token}", "latency_ms": 530, "model": model})
            if "MATRIX_STABLE_" in message:
                return httpx.Response(200, json={"message": "stable", "latency_ms": 505, "model": model})
            return httpx.Response(200, json={"message": "ok", "latency_ms": 500, "model": model})
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_validate_companion_provider_runtime_matrix_accepts_valid_payload(tmp_path: Path) -> None:
    """Layer: contract. Verifies schema validator accepts matrix payloads produced by the runner."""
    output = tmp_path / "matrix.json"
    schema = Path("docs/specs/companion-provider-runtime-matrix.schema.json").resolve()
    run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        rig_classes=["A", "B", "C", "D"],
        usage_profiles=["chat-first", "memory-heavy", "voice-heavy"],
        session_id="matrix",
        timeout_s=5.0,
        stability_attempts=2,
        output_path=output,
        transport=_validator_transport(),
    )
    exit_code = main(["--input", str(output), "--schema", str(schema)])
    assert exit_code == 0


def test_validate_companion_provider_runtime_matrix_rejects_invalid_payload(tmp_path: Path) -> None:
    """Layer: contract. Verifies schema validator rejects payloads missing required matrix keys."""
    output = tmp_path / "invalid.json"
    schema = Path("docs/specs/companion-provider-runtime-matrix.schema.json").resolve()
    output.write_text(json.dumps({"status": "complete"}), encoding="utf-8")
    exit_code = main(["--input", str(output), "--schema", str(schema)])
    assert exit_code == 1


def test_validate_companion_provider_runtime_matrix_reports_missing_input(tmp_path: Path) -> None:
    """Layer: integration. Verifies validator fails fast when the matrix input file path is missing."""
    schema = Path("docs/specs/companion-provider-runtime-matrix.schema.json").resolve()
    with pytest.raises(SystemExit, match="E_COMPANION_MATRIX_VALIDATE_INPUT_MISSING"):
        main(["--input", str(tmp_path / "missing.json"), "--schema", str(schema)])
