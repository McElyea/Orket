from __future__ import annotations

import json
from pathlib import Path

import httpx

from scripts.companion.run_companion_provider_runtime_matrix import run_companion_provider_runtime_matrix


def _success_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/companion/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/v1/companion/chat":
            return httpx.Response(
                200,
                json={"message": "MATRIX_OK", "latency_ms": 640, "model": "fake"},
            )
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def _failure_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/companion/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/v1/companion/chat":
            return httpx.Response(503, json={"detail": "provider unavailable"})
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


def test_run_companion_provider_runtime_matrix_success_writes_diff_ledger(tmp_path: Path) -> None:
    """Layer: integration. Verifies matrix runner writes canonical JSON with diff_ledger on success."""
    output = tmp_path / "matrix.json"
    payload = run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        session_id="matrix",
        timeout_s=5.0,
        output_path=output,
        transport=_success_transport(),
    )

    assert payload["status"] == "complete"
    assert payload["observed_result"] == "success"
    assert payload["cases"][0]["result"] == "success"
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert isinstance(persisted.get("diff_ledger"), list)
    assert len(persisted["diff_ledger"]) == 1


def test_run_companion_provider_runtime_matrix_partial_appends_diff_ledger(tmp_path: Path) -> None:
    """Layer: integration. Verifies partial runs record blockers and append diff-ledger entries."""
    output = tmp_path / "matrix.json"
    run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=["ollama"],
        models=["qwen2.5-coder:7b"],
        session_id="matrix",
        timeout_s=5.0,
        output_path=output,
        transport=_success_transport(),
    )

    payload = run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=["lmstudio"],
        models=["qwen2.5-coder:7b"],
        session_id="matrix",
        timeout_s=5.0,
        output_path=output,
        transport=_failure_transport(),
    )

    assert payload["status"] == "partial"
    assert payload["observed_result"] == "partial success"
    assert payload["cases"][0]["result"] == "failure"
    assert payload["blockers"][0]["provider"] == "lmstudio"
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert len(persisted["diff_ledger"]) == 2


def test_run_companion_provider_runtime_matrix_forwards_provider_and_model_in_chat_payload(tmp_path: Path) -> None:
    """Layer: integration. Verifies matrix runner forwards provider/model selectors through chat API payload."""
    captured: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/companion/config":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/api/v1/companion/chat":
            payload = json.loads(request.content.decode("utf-8"))
            captured.append(payload)
            return httpx.Response(200, json={"message": "MATRIX_OK", "latency_ms": 700, "model": "fake"})
        return httpx.Response(404, json={"detail": "not found"})

    output = tmp_path / "matrix.json"
    run_companion_provider_runtime_matrix(
        base_url="http://test",
        api_key="",
        providers=["lmstudio"],
        models=["qwen2.5-coder:14b"],
        session_id="matrix",
        timeout_s=5.0,
        output_path=output,
        transport=httpx.MockTransport(handler),
    )
    assert len(captured) == 1
    assert captured[0]["provider"] == "lmstudio"
    assert captured[0]["model"] == "qwen2.5-coder:14b"
