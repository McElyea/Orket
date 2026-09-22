"""Layer: integration. Actual API requests and readiness-report observations."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from orket.interfaces.api import create_api_app
from orket.settings import set_runtime_settings_context
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_construction_inputs import captured_environment
from tests.integration.test_api_run_observation_ownership import hold_native_read

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _unlock_payload(unlocked):
    failures = [] if unlocked else ["closed"]
    return {"unlocked": unlocked, "failures": [] if unlocked else ["gate: closed"],
            "criteria": {"gate": {"ok": unlocked, "failures": failures}}}


async def test_request_uses_one_report_observation_and_next_request_observes_changes(tmp_path, monkeypatch):
    report = tmp_path / "unlock.json"
    await asyncio.to_thread(report.write_text, json.dumps(_unlock_payload(True)), encoding="utf-8")
    await asyncio.to_thread((tmp_path / "outbound.json").write_text,
                            '{"policy_version":"runtime-policy-input-test"}', encoding="utf-8")
    monkeypatch.delenv("ORKET_ENABLE_MICROSERVICES", raising=False)
    monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_microservices")
    monkeypatch.setenv("ORKET_MICROSERVICES_UNLOCK_REPORT", str(report))
    monkeypatch.setenv("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", str(tmp_path / "missing-pilot.json"))
    environment = dict(captured_environment(), ORKET_DURABLE_ROOT=str(tmp_path / "state"))
    set_runtime_settings_context(user_settings={}, user_preferences={})
    app = create_api_app(project_root=tmp_path, environment=environment)
    real_read = Path.read_text
    observed = []

    def rotate_after_actual_read(path, *args, **kwargs):
        content = real_read(path, *args, **kwargs)
        if path == report:
            observed.append(content)
            if len(observed) == 1:
                # Keep the actual first read; change the real file before any subsequent read.
                report.write_text(json.dumps(_unlock_payload(False)), encoding="utf-8")
        return content

    async with app.router.lifespan_context(app):
        monkeypatch.setattr(Path, "read_text", rotate_after_actual_read)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://policy.test") as client:
            response = await client.get("/v1/system/runtime-policy", headers={"X-API-Key": TEST_API_KEY})
            assert response.status_code == 200
            first = response.json()
            assert first["architecture_mode"] == "force_microservices"
            assert first["microservices_unlocked"] is True
            assert first["allowed_architecture_patterns"] == ["monolith", "microservices"]
            assert len(observed) == 1
            response = await client.get("/v1/system/runtime-policy", headers={"X-API-Key": TEST_API_KEY})
            assert response.status_code == 200
            second = response.json()
            assert second["architecture_mode"] == "force_monolith"
            assert second["microservices_unlocked"] is False
            assert second["allowed_architecture_patterns"] == ["monolith"]
            assert len(observed) == 2
    assert app.state.api_runtime_context.closed


@pytest.mark.parametrize("method,route", [
    ("GET", "/v1/system/runtime-policy"), ("GET", "/v1/settings"), ("PATCH", "/v1/settings"),
])
async def test_request_environment_survives_report_read_suspension(tmp_path, monkeypatch, method, route):
    report = tmp_path / "unlock.json"
    await asyncio.to_thread(report.write_text, json.dumps(_unlock_payload(True)), encoding="utf-8")
    await asyncio.to_thread((tmp_path / "outbound.json").write_text,
                            '{"policy_version":"runtime-policy-input-test"}', encoding="utf-8")
    monkeypatch.delenv("ORKET_ENABLE_MICROSERVICES", raising=False)
    monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_microservices")
    monkeypatch.setenv("ORKET_MICROSERVICES_UNLOCK_REPORT", str(report))
    monkeypatch.setenv("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", str(tmp_path / "missing-pilot.json"))
    environment = dict(captured_environment(), ORKET_DURABLE_ROOT=str(tmp_path / "state"))
    set_runtime_settings_context(user_settings={}, user_preferences={})
    app = create_api_app(project_root=tmp_path, environment=environment)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://policy.test", headers={"X-API-Key": TEST_API_KEY},
    ) as client:
        state = hold_native_read(monkeypatch, report, False)
        arguments = {"json": {"architecture_mode": "force_microservices"}} if method == "PATCH" else {}
        request = asyncio.create_task(client.request(method, route, **arguments))
        try:
            assert await asyncio.to_thread(state.entered.wait, 5)
            monkeypatch.setenv("ORKET_ARCHITECTURE_MODE", "force_monolith")
            monkeypatch.setenv("ORKET_ENABLE_MICROSERVICES", "false")
            state.release.set()
            response = await asyncio.wait_for(request, 5)
            assert response.status_code == 200, response.text
            payload = response.json()
            if route == "/v1/system/runtime-policy":
                assert payload["architecture_mode"] == "force_microservices"
                assert payload["microservices_unlocked"] is True
            else:
                selected = payload["settings"]["architecture_mode"]
                assert selected["value"] == "force_microservices" and "policy_guard" not in selected
                assert "force_microservices" in selected["allowed_values"]
            next_response = await client.get("/v1/system/runtime-policy")
            assert next_response.status_code == 200
            assert next_response.json()["architecture_mode"] == "force_monolith"
            assert next_response.json()["microservices_unlocked"] is False
        finally:
            state.release.set()
            await asyncio.gather(request, return_exceptions=True)
            assert state.finished.is_set() and all(stream.closed for stream in state.files)
    assert app.state.api_runtime_context.closed
