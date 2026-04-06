# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import httpx

from scripts.companion.run_companion_provider_runtime_matrix import run_companion_provider_runtime_matrix


def _build_matrix_transport(
    *,
    fail_reasoning_provider: str = "",
    fail_voice: bool = False,
    stt_available: bool = True,
    capture: list[dict[str, object]] | None = None,
) -> httpx.MockTransport:
    memory_tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/status":
            return httpx.Response(200, json={"ok": True, "stt_available": stt_available})

        if request.url.path == "/api/config":
            return httpx.Response(200, json={"ok": True})

        if request.url.path == "/api/voice/control":
            if fail_voice:
                return httpx.Response(503, json={"detail": "voice unavailable"})
            payload = json.loads(request.content.decode("utf-8"))
            command = str(payload.get("command") or "")
            if command == "start":
                return httpx.Response(200, json={"ok": True, "state": "listening"})
            if command == "stop":
                return httpx.Response(200, json={"ok": True, "state": "idle"})
            if command == "submit":
                return httpx.Response(200, json={"ok": True, "state": "processing"})
            return httpx.Response(400, json={"detail": "bad voice command"})

        if request.url.path == "/api/chat":
            payload = json.loads(request.content.decode("utf-8"))
            if capture is not None:
                capture.append(payload)
            provider = str(payload.get("provider") or "")
            session_id = str(payload.get("session_id") or "")
            message = str(payload.get("message") or "")
            model = str(payload.get("model") or "")

            if fail_reasoning_provider and provider == fail_reasoning_provider and "17 * 19" in message:
                return httpx.Response(503, json={"detail": "provider unavailable"})

            if "17 * 19" in message:
                return httpx.Response(200, json={"message": "323", "latency_ms": 520, "model": model})
            if "MODE_OK" in message:
                return httpx.Response(200, json={"message": "Tutor: MODE_OK", "latency_ms": 610, "model": model})
            if "feel overwhelmed" in message:
                return httpx.Response(
                    200,
                    json={
                        "message": "I understand this feels heavy. Try one five-minute next step and then pause.",
                        "latency_ms": 760,
                        "model": model,
                    },
                )
            if "Remember this for later" in message:
                token = message.split("favorite_color=", 1)[-1].split(".", 1)[0].strip()
                memory_tokens[session_id] = token
                return httpx.Response(200, json={"message": "Stored", "latency_ms": 490, "model": model})
            if "What favorite_color" in message:
                token = memory_tokens.get(session_id, "missing")
                return httpx.Response(200, json={"message": f"favorite_color={token}", "latency_ms": 530, "model": model})
            if "MATRIX_STABLE_" in message:
                return httpx.Response(200, json={"message": "stable", "latency_ms": 500, "model": model})
            return httpx.Response(200, json={"message": "ok", "latency_ms": 500, "model": model})

        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def _run_matrix(
    *,
    output: Path,
    providers: list[str],
    models: list[str],
    transport: httpx.BaseTransport,
) -> dict[str, object]:
    return run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=providers,
        models=models,
        rig_classes=["A", "B", "C", "D"],
        usage_profiles=["chat-first", "memory-heavy", "voice-heavy"],
        session_id="matrix",
        timeout_s=5.0,
        stability_attempts=2,
        output_path=output,
        transport=transport,
    )


def test_run_companion_provider_runtime_matrix_complete_writes_recommendations_and_diff_ledger(tmp_path: Path) -> None:
    """Layer: integration. Verifies full success path writes matrix recommendations and diff_ledger."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        transport=_build_matrix_transport(),
    )

    assert payload["status"] == "complete"
    assert payload["observed_result"] == "success"
    assert payload["summary"]["successful_cases"] == 1
    assert payload["blockers"] == []
    recommendation = payload["recommendations"]["by_rig_class"]["A"]["chat-first"]
    assert recommendation["status"] == "recommended"
    assert recommendation["provider"] == "ollama"

    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(persisted.get("diff_ledger"), list)
    assert len(persisted["diff_ledger"]) == 1


def test_run_companion_provider_runtime_matrix_partial_when_voice_probe_fails(tmp_path: Path) -> None:
    """Layer: integration. Verifies voice probe failures produce degraded path and partial matrix status."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        transport=_build_matrix_transport(fail_voice=True),
    )

    assert payload["status"] == "partial"
    assert payload["observed_result"] == "partial success"
    assert payload["cases"][0]["observed_path"] == "degraded"
    steps = {row["step"] for row in payload["blockers"]}
    assert "voice_probe" in steps


def test_run_companion_provider_runtime_matrix_partial_when_coverage_dimension_not_measured(tmp_path: Path) -> None:
    """Layer: integration. Verifies unknown model-size paths produce explicit coverage blockers."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["ollama"],
        models=["mystery-model"],
        transport=_build_matrix_transport(),
    )

    assert payload["status"] == "partial"
    assert payload["observed_result"] == "partial success"
    coverage_rows = [row for row in payload["blockers"] if row["category"] == "coverage"]
    assert len(coverage_rows) == 1
    assert "footprint" in coverage_rows[0]["error"]


def test_run_companion_provider_runtime_matrix_failure_when_required_chat_step_blocks(tmp_path: Path) -> None:
    """Layer: integration. Verifies required-step chat failures are reported as blocked failures with exact step."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["lmstudio"],
        models=["qwen2.5-coder:14b"],
        transport=_build_matrix_transport(fail_reasoning_provider="lmstudio"),
    )

    assert payload["status"] == "partial"
    assert payload["observed_result"] == "failure"
    assert payload["cases"][0]["result"] == "failure"
    assert payload["cases"][0]["failed_step"] == "chat_reasoning"


def test_run_companion_provider_runtime_matrix_forwards_provider_and_model_in_chat_payload(tmp_path: Path) -> None:
    """Layer: integration. Verifies matrix runner forwards provider/model selectors through chat API payload."""
    captured: list[dict[str, object]] = []
    output = tmp_path / "matrix.json"
    _run_matrix(
        output=output,
        providers=["lmstudio"],
        models=["qwen2.5-coder:14b"],
        transport=_build_matrix_transport(capture=captured),
    )
    assert len(captured) > 0
    assert all(row["provider"] == "lmstudio" for row in captured)
    assert all(row["model"] == "qwen2.5-coder:14b" for row in captured)


def test_run_companion_provider_runtime_matrix_recommendation_matrix_reflects_rig_fit(tmp_path: Path) -> None:
    """Layer: integration. Verifies recommendation matrix selects smaller models for Class A and larger for Class D."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["ollama", "lmstudio"],
        models=["qwen2.5-coder:7b", "qwen2.5-coder:40b"],
        transport=_build_matrix_transport(),
    )

    assert payload["status"] == "complete"
    class_a = payload["recommendations"]["by_rig_class"]["A"]["chat-first"]
    class_d = payload["recommendations"]["by_rig_class"]["D"]["chat-first"]
    assert class_a["model"] == "qwen2.5-coder:7b"
    assert class_d["model"] == "qwen2.5-coder:40b"


def test_run_companion_provider_runtime_matrix_expands_single_provider_multi_model_inputs(tmp_path: Path) -> None:
    """Layer: integration. Verifies single-provider multi-model input expands into one case per model."""
    output = tmp_path / "matrix.json"
    payload = _run_matrix(
        output=output,
        providers=["ollama"],
        models=["qwen2.5-coder:7b", "qwen2.5-coder:14b"],
        transport=_build_matrix_transport(),
    )
    assert payload["summary"]["requested_cases"] == 2
    assert len(payload["cases"]) == 2
    models_seen = {row["model"] for row in payload["case_pairs_requested"]}
    assert models_seen == {"qwen2.5-coder:7b", "qwen2.5-coder:14b"}
