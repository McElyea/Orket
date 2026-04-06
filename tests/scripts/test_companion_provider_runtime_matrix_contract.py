# LIFECYCLE: live
from __future__ import annotations

import json
from pathlib import Path

import httpx

from scripts.companion.run_companion_provider_runtime_matrix import run_companion_provider_runtime_matrix


def _contract_transport(*, fail_status: bool = False) -> httpx.MockTransport:
    memory_tokens: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/status":
            if fail_status:
                return httpx.Response(503, json={"detail": "status offline"})
            return httpx.Response(200, json={"ok": True, "stt_available": True})
        if request.url.path == "/api/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/voice/control":
            payload = json.loads(request.content.decode("utf-8"))
            command = str(payload.get("command") or "")
            state_map = {"start": "listening", "stop": "idle", "submit": "processing"}
            return httpx.Response(200, json={"ok": True, "state": state_map.get(command, "idle")})
        if request.url.path == "/api/chat":
            payload = json.loads(request.content.decode("utf-8"))
            message = str(payload.get("message") or "")
            session_id = str(payload.get("session_id") or "")
            model = str(payload.get("model") or "")
            if "17 * 19" in message:
                return httpx.Response(200, json={"message": "323", "latency_ms": 500, "model": model})
            if "MODE_OK" in message:
                return httpx.Response(200, json={"message": "Tutor: MODE_OK", "latency_ms": 610, "model": model})
            if "feel overwhelmed" in message:
                return httpx.Response(200, json={"message": "I understand; try one next step.", "latency_ms": 740, "model": model})
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


def test_companion_provider_runtime_matrix_contract_complete_payload_shape(tmp_path: Path) -> None:
    """Layer: contract. Verifies complete matrix payload includes required top-level, case, score, and summary keys."""
    output = tmp_path / "matrix.json"
    payload = run_companion_provider_runtime_matrix(
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
        transport=_contract_transport(),
    )

    required_keys = {
        "generated_at_utc",
        "status",
        "observed_result",
        "providers_requested",
        "models_requested",
        "case_pairs_requested",
        "rig_classes_requested",
        "usage_profiles_requested",
        "cases",
        "recommendations",
        "blockers",
        "summary",
        "diff_ledger",
    }
    assert required_keys.issubset(set(payload.keys()))
    assert payload["status"] == "complete"
    assert payload["observed_result"] == "success"
    assert payload["summary"]["requested_cases"] == 1
    assert payload["summary"]["successful_cases"] == 1
    assert payload["summary"]["failed_cases"] == 0

    case = payload["cases"][0]
    assert {"provider", "model", "observed_path", "result", "scores"}.issubset(set(case.keys()))
    score_keys = {
        "reasoning",
        "conversational_quality",
        "memory_usefulness",
        "latency",
        "footprint",
        "voice_suitability",
        "stability",
        "mode_adherence",
    }
    assert score_keys == set(case["scores"].keys())


def test_companion_provider_runtime_matrix_contract_partial_payload_shape(tmp_path: Path) -> None:
    """Layer: contract. Verifies partial matrix payload with blocked case retains blocker and summary semantics."""
    output = tmp_path / "matrix.json"
    payload = run_companion_provider_runtime_matrix(
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
        transport=_contract_transport(fail_status=True),
    )

    assert payload["status"] == "partial"
    assert payload["observed_result"] == "failure"
    assert payload["summary"]["requested_cases"] == 1
    assert payload["summary"]["successful_cases"] == 0
    assert payload["summary"]["failed_cases"] == 1
    assert payload["summary"]["blocker_count"] >= 1
    assert payload["cases"][0]["result"] == "failure"
    assert payload["cases"][0]["failed_step"] == "status"
    assert payload["blockers"][0]["step"] == "status"
