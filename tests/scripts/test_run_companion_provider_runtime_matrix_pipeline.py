# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import httpx

from scripts.companion.run_companion_provider_runtime_matrix_pipeline import run_matrix_pipeline


def _pipeline_transport(*, fail_status: bool = False) -> httpx.MockTransport:
    memory_tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/status":
            if fail_status:
                return httpx.Response(503, json={"detail": "status unavailable"})
            return httpx.Response(200, json={"ok": True, "stt_available": True})
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/voice/control":
            payload = json.loads(request.content.decode("utf-8"))
            state = {"start": "listening", "stop": "idle", "submit": "processing"}.get(str(payload.get("command") or ""), "idle")
            return httpx.Response(200, json={"ok": True, "state": state})
        if request.url.path == "/api/chat":
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


def test_run_companion_provider_runtime_matrix_pipeline_success_writes_report_and_validates(tmp_path: Path) -> None:
    """Layer: integration. Verifies pipeline run writes JSON+markdown outputs and produces zero schema validation errors on success."""
    output = tmp_path / "matrix.json"
    report = tmp_path / "README.md"
    schema = Path("docs/specs/companion-provider-runtime-matrix.schema.json").resolve()
    result = run_matrix_pipeline(
        base_url="http://test",
        api_key="",
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        provider_model_map="",
        rig_classes=["A", "B", "C", "D"],
        usage_profiles=["chat-first", "memory-heavy", "voice-heavy"],
        session_id="matrix",
        timeout_s=5.0,
        stability_attempts=2,
        output_path=output,
        report_output_path=report,
        schema_path=schema,
        transport=_pipeline_transport(),
    )
    payload = dict(result["payload"])
    assert payload["status"] == "complete"
    assert result["validation_errors"] == []
    assert output.exists()
    assert report.exists()


def test_run_companion_provider_runtime_matrix_pipeline_partial_still_writes_report(tmp_path: Path) -> None:
    """Layer: integration. Verifies pipeline still emits report output when live matrix path is blocked/partial."""
    output = tmp_path / "matrix.json"
    report = tmp_path / "README.md"
    schema = Path("docs/specs/companion-provider-runtime-matrix.schema.json").resolve()
    result = run_matrix_pipeline(
        base_url="http://test",
        api_key="",
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        provider_model_map="",
        rig_classes=["A", "B", "C", "D"],
        usage_profiles=["chat-first", "memory-heavy", "voice-heavy"],
        session_id="matrix",
        timeout_s=5.0,
        stability_attempts=2,
        output_path=output,
        report_output_path=report,
        schema_path=schema,
        transport=_pipeline_transport(fail_status=True),
    )
    payload = dict(result["payload"])
    assert payload["status"] == "partial"
    assert output.exists()
    assert report.exists()
