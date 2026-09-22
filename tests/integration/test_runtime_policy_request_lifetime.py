"""Layer: integration. Policy requests retain real report reads and API shutdown."""
import asyncio
import json

import httpx
import pytest

from orket.interfaces.api import create_api_app
from orket.settings import set_runtime_settings_context
from tests.helpers.api_observation_lifetime import exercise_owned_api_read
from tests.helpers.outward_authorization import TEST_API_KEY
from tests.integration.test_api_construction_inputs import captured_environment
from tests.integration.test_api_run_observation_ownership import hold_native_read
from tests.integration.test_runtime_policy_request_inputs import _unlock_payload

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["cancel", "timeout", "worker_failure", "shutdown", "shutdown_cancel"])
async def test_policy_request_keeps_its_admitted_report_read(tmp_path, monkeypatch, record_property, stop):
    report = tmp_path / "unlock.json"
    await asyncio.to_thread(report.write_text, json.dumps(_unlock_payload(True)), encoding="utf-8")
    await asyncio.to_thread((tmp_path / "outbound.json").write_text,
                            '{"policy_version":"runtime-policy-lifetime-test"}', encoding="utf-8")
    monkeypatch.delenv("ORKET_ENABLE_MICROSERVICES", raising=False)
    monkeypatch.setenv("ORKET_MICROSERVICES_UNLOCK_REPORT", str(report))
    monkeypatch.setenv("ORKET_MICROSERVICES_PILOT_STABILITY_REPORT", str(tmp_path / "missing-pilot.json"))
    environment = dict(captured_environment(), ORKET_DURABLE_ROOT=str(tmp_path / "state"))
    set_runtime_settings_context(user_settings={}, user_preferences={})
    app = create_api_app(project_root=tmp_path, environment=environment)
    async with app.router.lifespan_context(app), httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://policy.test", headers={"X-API-Key": TEST_API_KEY},
    ) as client:
        state = hold_native_read(monkeypatch, report, stop == "worker_failure")
        await exercise_owned_api_read(app, client, "/v1/system/runtime-policy/options", state,
                                      tmp_path, record_property, stop)
    assert app.state.api_runtime_context.closed
