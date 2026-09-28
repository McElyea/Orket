"""Layer: integration. Selected HTTP construction ports survive the owner-scheduling gap."""
import asyncio
from types import SimpleNamespace

import pytest

from orket.adapters.execution.sandbox_http import SandboxHttpAdapter
from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.fixture_input_controls import selected_time
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.runtime_verification_hold import sqlite_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("changed", ["factory", "timeout"])
async def test_http_factory_and_timeout_are_captured_before_owner_admission(tmp_path, record_property, changed):
    entered, release = asyncio.Event(), asyncio.Event()
    mutations, factory_calls = [], []

    async def respond(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), 5)
        return 200, 7

    def selected_factory(timeout):
        assert mutations == [changed], "the mutation must occur before transport construction"
        factory_calls.append(timeout)
        return SandboxHttpAdapter(timeout)

    service = SandboxVerificationService(utc_now=selected_time, timeout_s=2.0, http_factory=selected_factory)

    def mutate():
        mutations.append(changed)
        if changed == "factory":
            service.http_factory = lambda _timeout: pytest.fail("replacement factory selected")
        else:
            service.timeout_s = 0.001

    verification = IssueVerification(scenarios=[VerificationScenario(id="http", description="captured ports",
        input_data={"endpoint": "/probe"}, expected_output=7)])
    async with observed_http_server(respond) as (url, requests):
        task = asyncio.create_task(service.verify_sandbox(SimpleNamespace(id="capture", api_url=url), verification))
        asyncio.get_running_loop().call_soon(mutate)
        try:
            await asyncio.wait_for(entered.wait(), 5)
            assert factory_calls == [2.0] and not task.done()
            assert await sqlite_response(tmp_path / "response.sqlite3", record_property) < 0.5
            release.set()
            result = await task
            assert result.passed == 1 and len(requests) == 1
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
