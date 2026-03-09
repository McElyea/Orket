from __future__ import annotations

import json

import httpx

from scripts.companion.companion_matrix_execution import coverage_blockers, evaluate_case


def _execution_transport(
    *,
    status_fails: bool = False,
    mode_config_fails: bool = False,
    voice_fails: bool = False,
    stt_available: bool = True,
) -> httpx.MockTransport:
    memory_tokens: dict[str, str] = {}
    config_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal config_calls
        if request.url.path == "/api/v1/companion/status":
            if status_fails:
                return httpx.Response(503, json={"detail": "status unavailable"})
            return httpx.Response(200, json={"ok": True, "stt_available": stt_available})

        if request.url.path == "/api/v1/companion/config":
            config_calls += 1
            if mode_config_fails and config_calls > 1:
                return httpx.Response(503, json={"detail": "mode config unavailable"})
            return httpx.Response(200, json={"ok": True})

        if request.url.path == "/api/v1/companion/voice/control":
            if voice_fails:
                return httpx.Response(503, json={"detail": "voice offline"})
            payload = json.loads(request.content.decode("utf-8"))
            command = str(payload.get("command") or "")
            if command == "start":
                return httpx.Response(200, json={"ok": True, "state": "listening"})
            if command == "stop":
                return httpx.Response(200, json={"ok": True, "state": "idle"})
            if command == "submit":
                return httpx.Response(200, json={"ok": True, "state": "processing"})
            return httpx.Response(400, json={"detail": "invalid command"})

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
                return httpx.Response(
                    200,
                    json={
                        "message": "I understand this feels heavy. Try one next step and rest.",
                        "latency_ms": 740,
                        "model": model,
                    },
                )
            if "Remember this for later" in message:
                token = message.split("favorite_color=", 1)[-1].split(".", 1)[0].strip()
                memory_tokens[session_id] = token
                return httpx.Response(200, json={"message": "stored", "latency_ms": 490, "model": model})
            if "What favorite_color" in message:
                token = memory_tokens.get(session_id, "missing")
                return httpx.Response(200, json={"message": f"favorite_color={token}", "latency_ms": 520, "model": model})
            if "MATRIX_STABLE_" in message:
                return httpx.Response(200, json={"message": "stable", "latency_ms": 510, "model": model})
            return httpx.Response(200, json={"message": "ok", "latency_ms": 500, "model": model})

        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_evaluate_case_success_returns_primary_path_with_measured_scores() -> None:
    """Layer: integration. Verifies evaluate_case returns primary success with measured score dimensions when all steps pass."""
    with httpx.Client(base_url="http://test", transport=_execution_transport()) as client:
        case, blockers = evaluate_case(
            client=client,
            session_id="s1",
            provider="ollama",
            model="qwen2.5-coder:7b",
            stability_attempts=2,
        )
    assert case["result"] == "success"
    assert case["observed_path"] == "primary"
    assert blockers == []
    assert case["scores"]["reasoning"]["status"] == "measured"
    assert case["scores"]["voice_suitability"]["status"] == "measured"


def test_evaluate_case_voice_failures_degrade_path_and_emit_blocker() -> None:
    """Layer: integration. Verifies voice-control probe failures degrade an otherwise successful case and emit blocker evidence."""
    with httpx.Client(base_url="http://test", transport=_execution_transport(voice_fails=True)) as client:
        case, blockers = evaluate_case(
            client=client,
            session_id="s1",
            provider="ollama",
            model="qwen2.5-coder:7b",
            stability_attempts=2,
        )
    assert case["result"] == "success"
    assert case["observed_path"] == "degraded"
    assert len(blockers) == 1
    assert blockers[0]["step"] == "voice_probe"


def test_evaluate_case_status_failure_blocks_case() -> None:
    """Layer: integration. Verifies status endpoint failures stop evaluation and return a blocked failure case."""
    with httpx.Client(base_url="http://test", transport=_execution_transport(status_fails=True)) as client:
        case, blockers = evaluate_case(
            client=client,
            session_id="s1",
            provider="ollama",
            model="qwen2.5-coder:7b",
            stability_attempts=2,
        )
    assert case["result"] == "failure"
    assert case["failed_step"] == "status"
    assert blockers[0]["step"] == "status"


def test_evaluate_case_mode_config_failure_blocks_case() -> None:
    """Layer: integration. Verifies mode-probe config failure is surfaced with explicit failing step context."""
    with httpx.Client(base_url="http://test", transport=_execution_transport(mode_config_fails=True)) as client:
        case, blockers = evaluate_case(
            client=client,
            session_id="s1",
            provider="ollama",
            model="qwen2.5-coder:7b",
            stability_attempts=2,
        )
    assert case["result"] == "failure"
    assert case["failed_step"] == "config_mode_probe"
    assert blockers[0]["step"] == "config_mode_probe"


def test_coverage_blockers_flags_not_measured_dimensions() -> None:
    """Layer: contract. Verifies coverage_blockers emits explicit coverage blockers for non-measured score dimensions."""
    rows = [
        {
            "provider": "ollama",
            "model": "mystery-model",
            "result": "success",
            "scores": {
                "reasoning": {"status": "measured", "value": 1.0},
                "conversational_quality": {"status": "measured", "value": 1.0},
                "memory_usefulness": {"status": "measured", "value": 1.0},
                "latency": {"status": "measured", "value": 1.0},
                "footprint": {"status": "not_measured", "value": None},
                "voice_suitability": {"status": "measured", "value": 1.0},
                "stability": {"status": "measured", "value": 1.0},
                "mode_adherence": {"status": "measured", "value": 1.0},
            },
        }
    ]
    blockers = coverage_blockers(rows)
    assert len(blockers) == 1
    assert blockers[0]["category"] == "coverage"
    assert "footprint" in blockers[0]["error"]
