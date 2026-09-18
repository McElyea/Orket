"""Layer: integration. Real HTTP observations must match captured expectations."""
import asyncio
from types import SimpleNamespace

import pytest

from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def verification_for(expected):
    return IssueVerification(scenarios=[VerificationScenario(
        id="observed", description="Compare actual response", input_data={"endpoint": "/probe"},
        expected_output=expected,
    )])


@pytest.mark.parametrize("expected", [0, False, "", [], {}, None], ids=["zero", "false", "empty-string", "empty-list", "empty-object", "null"])
@pytest.mark.parametrize("matches", [True, False], ids=["matching", "different"])
async def test_http_verification_compares_falsy_expected_values(expected, matches):
    actual = expected if matches else {"unexpected": True}

    async def respond(_request):
        return 200, actual

    async with observed_http_server(respond) as (url, requests):
        verification = verification_for(expected)
        result = await SandboxVerificationService().verify_sandbox(SimpleNamespace(id="observed", api_url=url), verification)
        assert [request[0].split()[:2] for request in requests] == [["GET", "/probe"]]
        assert result.total_scenarios == 1
        assert (result.passed, result.failed) == ((1, 0) if matches else (0, 1))
        assert verification.scenarios[0].status == ("pass" if matches else "fail")


async def test_http_verification_captures_expectations_before_waiting_for_response():
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=5)
        return 200, {"unexpected": True}

    async with observed_http_server(respond) as (url, requests):
        verification = verification_for({"expected": "original"})
        task = asyncio.create_task(SandboxVerificationService().verify_sandbox(SimpleNamespace(id="observed", api_url=url), verification))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            verification.scenarios[0].expected_output.clear()
            verification.scenarios[0].expected_output.update({"unexpected": True})
        finally:
            release.set()
            result = await asyncio.wait_for(task, timeout=5)
        assert len(requests) == 1
        assert (result.passed, result.failed) == (0, 1)


async def test_http_verification_captures_remaining_target_method_and_body():
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        if request[0].split()[1] == "/first":
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=5)
            return 200, "first"
        return 201, request[1]

    async with observed_http_server(respond) as (url, requests), observed_http_server(respond) as (other, diverted):
        verification = IssueVerification(scenarios=[
            VerificationScenario(id="first", description="hold", input_data={"endpoint": "/first"}, expected_output="first"),
            VerificationScenario(id="second", description="captured", input_data={
                "endpoint": "/second", "method": "POST", "payload": {"nested": [1]}, "expected_status": 201,
            }, expected_output={"nested": [1]}),
        ])
        sandbox = SimpleNamespace(id="original", api_url=url)
        task = asyncio.create_task(SandboxVerificationService().verify_sandbox(sandbox, verification))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            sandbox.id, sandbox.api_url = "diverted", other
            second = verification.scenarios[1]
            second.input_data["payload"]["nested"].append(2)
            second.input_data.update(endpoint="/diverted", method="DELETE", expected_status=503)
            second.expected_output["nested"].append(2)
            verification.scenarios.reverse()
        finally:
            release.set()
            result = await asyncio.wait_for(task, timeout=5)
        assert (result.passed, result.failed) == (2, 0)
        assert not diverted and len(requests) == 2
        assert requests[1] == ("POST /second HTTP/1.1", {"nested": [1]})
        assert "original" in result.logs[0] and "diverted" not in result.logs[0]
        assert f"Target URL: {url}" in result.logs and not any(other in line for line in result.logs)
        assert [scenario.id for scenario in verification.scenarios] == ["first", "second"]


@pytest.mark.parametrize("status,body,content_type,expected,passes", [
    (503, {}, "application/json", {}, False),
    (200, b"{", "application/json", {}, False),
    (200, False, "application/json", 0, False),
    (200, 1.0, "application/json", 1, False),
    (200, b"plain", "text/plain", "plain", True),
])
async def test_http_observation_requires_status_parsed_body_and_exact_types(status, body, content_type, expected, passes):
    async def respond(_request):
        return status, body

    async with observed_http_server(respond, content_type=content_type) as (url, requests):
        verification = verification_for(expected)
        result = await SandboxVerificationService().verify_sandbox(SimpleNamespace(id="observed", api_url=url), verification)
        assert len(requests) == 1
        assert (result.passed, result.failed) == ((1, 0) if passes else (0, 1))


async def test_held_http_request_does_not_block_another_verification(record_testsuite_property):
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        if request[0].split()[1] == "/held":
            entered.set()
            await asyncio.wait_for(release.wait(), timeout=5)
        return 200, {}

    async with observed_http_server(respond) as (url, requests):
        service = SandboxVerificationService()
        sandbox = SimpleNamespace(id="observed", api_url=url)
        held = verification_for({})
        held.scenarios[0].input_data["endpoint"] = "/held"
        task = asyncio.create_task(service.verify_sandbox(sandbox, held))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            started = asyncio.get_running_loop().time()
            fast = await asyncio.wait_for(service.verify_sandbox(sandbox, verification_for({})), timeout=0.5)
            elapsed = asyncio.get_running_loop().time() - started
            record_testsuite_property("concurrent_http_elapsed_s", elapsed)
            assert elapsed < 0.5 and fast.passed == 1 and not task.done()
        finally:
            release.set()
            result = await asyncio.wait_for(task, timeout=5)
        assert result.passed == 1 and len(requests) == 2


async def test_http_transport_does_not_adopt_ambient_proxy(monkeypatch):
    async def respond(_request):
        return 200, {}

    async with observed_http_server(respond) as (url, requests), observed_http_server(respond) as (proxy, diverted):
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            monkeypatch.setenv(name, proxy)
        monkeypatch.setenv("NO_PROXY", "")
        result = await SandboxVerificationService().verify_sandbox(
            SimpleNamespace(id="observed", api_url=url), verification_for({}),
        )
        assert result.passed == 1 and len(requests) == 1 and not diverted
