from __future__ import annotations

import re
from typing import Any

import pytest

import orket.interfaces.api as api_module


@pytest.mark.integration
def test_health_is_minimal_and_unauthenticated(test_client) -> None:
    """Layer: integration. Verifies Phase 0 /health exposes only minimal unauthenticated status."""
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_v1_response_includes_orket_version_header(test_client) -> None:
    """Layer: integration. Verifies /v1 responses carry the required runtime version header."""
    response = test_client.get("/v1/version", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    assert response.headers["X-Orket-Version"] == api_module.__version__


@pytest.mark.integration
def test_all_registered_v1_routes_require_api_key_dependency(test_client) -> None:
    """Layer: integration. Every documented v1 operation rejects unauthenticated requests."""
    operations = [
        (method, path)
        for path, item in test_client.app.openapi()["paths"].items()
        if path.startswith("/v1/")
        for method in item
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    ]
    assert operations
    for method, path in operations:
        target = re.sub(r"\{[^}]+\}", "unauthenticated", path)
        response = test_client.request(method, target)
        assert response.status_code == 403, (method, path, response.status_code, response.text)


@pytest.mark.integration
def test_v1_response_path_traverses_outbound_policy_gate(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    """Layer: contract. Verifies a representative /v1 response calls the outbound policy gate before serialization."""
    calls: list[tuple[Any, dict[str, Any]]] = []

    def _fake_gate(payload: Any, config: dict[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
        calls.append((payload, dict(config or {})))
        return payload, {"applied": True}

    monkeypatch.setattr(api_module, "apply_outbound_policy_gate", _fake_gate)

    response = test_client.get("/v1/version", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200
    assert calls == [({"version": api_module.__version__, "api": "v1"}, {"surface": "api.version"})]


@pytest.mark.integration
def test_v1_auth_failure_logs_without_raw_key(monkeypatch: pytest.MonkeyPatch, test_client) -> None:
    """Layer: contract. Verifies auth rejection telemetry omits the provided API key value."""
    captured: list[tuple[str, dict[str, Any]]] = []

    def _fake_log_event(event: str, payload: dict[str, Any], *_args: Any, **_kwargs: Any) -> None:
        captured.append((event, payload))

    monkeypatch.setattr("orket.application.services.api_event_service.log_event", _fake_log_event)

    response = test_client.get("/v1/version", headers={"X-API-Key": "raw-secret-key"})

    assert response.status_code == 403
    assert captured == [
        (
            "api_auth_rejected",
            {
                "route_class": "core",
                "reason": "invalid_or_missing_key_for_core_route",
                "request_path": "/v1/version",
                "provided_key_present": True,
            },
        )
    ]
    assert "raw-secret-key" not in str(captured)
