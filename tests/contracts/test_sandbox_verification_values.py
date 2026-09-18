"""Layer: contract. Captured HTTP inputs and pure interpretation have one meaning."""
from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError
from orket.core.domain.sandbox_verifier import (
    SandboxHttpObservation,
    capture_sandbox_verification,
    interpret_sandbox_observations,
)
from orket.schema import IssueVerification, VerificationScenario
from orket_extension_sdk import FrozenJson

pytestmark = pytest.mark.contract
NOW = "2026-09-18T12:00:00+00:00"


def capture(verification, url="http://localhost"):
    return capture_sandbox_verification(sandbox_id="sandbox", base_url=url, timestamp=NOW, verification=verification)


def inputs():
    return IssueVerification(scenarios=[VerificationScenario(
        id="captured", description="exact", input_data={"endpoint": "/probe", "payload": {"nested": [1]}},
        expected_output={"nested": [1]},
    )])


def test_core_capture_and_interpretation_are_immutable_repeatable_and_detached():
    original = inputs()
    captured = capture(original)
    observations = (SandboxHttpObservation("captured", 200, FrozenJson.freeze({"nested": [1]})),)
    expected = interpret_sandbox_observations(captured, observations)
    original.scenarios[0].expected_output["nested"].append(2)
    captured.scenarios[0].request.payload.thaw()["nested"].append(2)
    first = interpret_sandbox_observations(captured, observations)
    assert first == expected and first[0].timestamp == NOW and first[0].passed == 1
    assert captured.base_url == "http://localhost" and "Target URL: http://localhost" in first[0].logs
    first[1][0].actual_output["nested"].append(3)
    first[0].logs.append("mutable result")
    assert interpret_sandbox_observations(captured, observations) == expected
    with pytest.raises(FrozenInstanceError):
        captured.timestamp = "changed"


@pytest.mark.parametrize("observations", [(), (SandboxHttpObservation("wrong"),),
    (SandboxHttpObservation("captured"), SandboxHttpObservation("extra"))])
def test_interpretation_refuses_incomplete_or_substituted_observations(observations):
    with pytest.raises(ValueError, match="E_SANDBOX_OBSERVATION_IDENTITY_MISMATCH"):
        interpret_sandbox_observations(capture(inputs()), observations)


@pytest.mark.parametrize("url", ["ftp://localhost", "http:///path", "http://user:secret@localhost",
    "http://localhost?query=1", "http://localhost#fragment", "http://localhost:bad", "http://localhost:0",
    "http://bad host", "http://local\nhost"])
def test_invalid_base_urls_refuse_before_dispatch(url):
    with pytest.raises(ValueError, match="E_SANDBOX_HTTP_BASE_URL_INVALID"):
        capture(inputs(), url)


@pytest.mark.parametrize("unsupported", [float("nan"), {"not-json"}, object()])
def test_unsupported_json_is_not_silently_coerced(unsupported):
    verification = inputs()
    verification.scenarios[0].expected_output = unsupported
    with pytest.raises(ProtocolCanonicalizationError):
        capture(verification)


def test_duplicate_scenario_ids_refuse_before_dispatch():
    verification = inputs()
    verification.scenarios.append(verification.scenarios[0].model_copy(deep=True))
    with pytest.raises(ValueError, match="E_SANDBOX_SCENARIO_ID_DUPLICATE"):
        capture(verification)


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [{}, {"endpoint": ""}, {"endpoint": "relative"},
    {"endpoint": "/probe", "method": "GET\r\ninvalid"}])
async def test_inadmissible_scenarios_fail_without_constructing_transport(invalid):
    def forbidden(_timeout):
        pytest.fail("No HTTP resource may be constructed for rejected requests")

    verification = inputs()
    verification.scenarios[0].input_data = invalid
    result = await SandboxVerificationService(http_factory=forbidden).verify_sandbox(
        SimpleNamespace(id="sandbox", api_url="http://localhost"), verification,
    )
    assert (result.total_scenarios, result.passed, result.failed) == (1, 0, 1)


@pytest.mark.asyncio
async def test_empty_verification_has_explicit_time_and_no_empirical_proof():
    def forbidden(_timeout):
        pytest.fail("Empty verification must not construct HTTP resources")

    clock = SimpleNamespace(utc_now_iso=lambda: NOW)
    result = await SandboxVerificationService(runtime_inputs=clock, http_factory=forbidden).verify_sandbox(
        SimpleNamespace(id="sandbox", api_url="http://localhost"), IssueVerification(),
    )
    assert (result.timestamp, result.total_scenarios, result.passed, result.failed) == (NOW, 0, 0, 0)
    assert any("no empirical proof" in line for line in result.logs)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_timeout_refuses_before_transport(timeout):
    with pytest.raises(ValueError, match="E_SANDBOX_HTTP_TIMEOUT_INVALID"):
        SandboxVerificationService(timeout_s=timeout)
