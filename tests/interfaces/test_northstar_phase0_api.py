from __future__ import annotations

from typing import Any

import pytest
from fastapi.routing import APIRoute

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


@pytest.mark.contract
def test_all_registered_v1_routes_require_api_key_dependency() -> None:
    """Layer: contract. Verifies registered /v1 routes use the shared X-API-Key dependency."""
    v1_routes = [
        route
        for route in api_module.app.routes
        if isinstance(route, APIRoute) and str(route.path).startswith("/v1/")
    ]

    assert v1_routes
    for route in v1_routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert api_module.get_api_key in dependency_calls, route.path


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

    monkeypatch.setattr(api_module, "log_event", _fake_log_event)

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
