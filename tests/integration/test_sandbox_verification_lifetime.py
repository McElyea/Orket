"""Layer: integration. Real HTTP cancellation/timeout retains observed client cleanup."""
import asyncio
from types import SimpleNamespace

import pytest

from orket.adapters.execution.sandbox_http import SandboxHttpAdapter
from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def verification():
    return IssueVerification(scenarios=[VerificationScenario(
        id=name, description=name, input_data={"endpoint": "/" + name}, expected_output={},
    ) for name in ("held", "never-dispatched")])


@pytest.mark.parametrize("cleanup_fails", [False, True], ids=["closed", "close-error"])
async def test_repeated_cancellation_retains_cleanup_and_stops_dispatch(cleanup_fails, record_testsuite_property):
    entered, release, closing, finish = (asyncio.Event() for _ in range(4))
    transports = []

    class HeldClose(SandboxHttpAdapter):
        async def __aexit__(self, *args):
            closing.set()
            await asyncio.wait_for(finish.wait(), timeout=5)
            await super().__aexit__(*args)
            if cleanup_fails:
                raise OSError("observed cleanup failure")

    def create(timeout):
        transport = HeldClose(timeout)
        transports.append(transport)
        return transport

    async def respond(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=5)
        return 200, {}

    async with observed_http_server(respond, allow_disconnect=True) as (url, requests):
        inputs = verification()
        before = inputs.model_dump()
        service = SandboxVerificationService(http_factory=create)
        task = asyncio.create_task(service.verify_sandbox(SimpleNamespace(id="observed", api_url=url), inputs))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            started = asyncio.get_running_loop().time()
            task.cancel()
            await asyncio.wait_for(closing.wait(), timeout=0.5)
            record_testsuite_property(f"cancel_to_cleanup_s_{cleanup_fails}", asyncio.get_running_loop().time() - started)
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not transports[0].client.is_closed
            assert len(requests) == 1 and inputs.model_dump() == before
        finally:
            finish.set()
            release.set()
            outcome, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)
        assert isinstance(outcome, OSError if cleanup_fails else asyncio.CancelledError)
        assert transports[0].client.is_closed
        assert len(requests) == 1 and inputs.model_dump() == before


async def test_real_http_timeout_closes_client_and_publishes_failure():
    entered, release = asyncio.Event(), asyncio.Event()
    transports = []

    def create(timeout):
        transport = SandboxHttpAdapter(timeout)
        transports.append(transport)
        return transport

    async def respond(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=5)
        return 200, {}

    async with observed_http_server(respond, allow_disconnect=True) as (url, requests):
        inputs = verification()
        inputs.scenarios = inputs.scenarios[:1]
        task = asyncio.create_task(SandboxVerificationService(timeout_s=0.1, http_factory=create).verify_sandbox(
            SimpleNamespace(id="observed", api_url=url), inputs,
        ))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            result = await asyncio.wait_for(task, timeout=2)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)
        assert len(requests) == 1 and transports[0].client.is_closed
        assert (result.passed, result.failed) == (0, 1)
        assert inputs.scenarios[0].status == "fail"
        assert any("ReadTimeout" in line for line in result.logs)
