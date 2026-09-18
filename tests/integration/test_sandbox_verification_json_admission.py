"""Layer: integration. Validate original scenario values before any HTTP dispatch."""
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ValidationError

from orket.application.services.sandbox_verification_service import SandboxVerificationService
from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError
from orket.schema import IssueVerification, VerificationScenario
from tests.helpers.observed_http_server import observed_http_server

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@dataclass
class DataclassValue:
    value: int


class ModelValue(BaseModel):
    value: int


def scenario(identity):
    return VerificationScenario(
        id=identity, description="Strict JSON admission",
        input_data={"endpoint": "/probe", "payload": {"value": 1}}, expected_output={"value": 1},
    )


@pytest.mark.parametrize("value", [DataclassValue(1), ModelValue(value=1)], ids=["dataclass", "model"])
@pytest.mark.parametrize("field", ["expected_output", "payload"])
async def test_unsupported_values_refuse_entire_batch_before_http(field, value):
    async def respond(_request):
        return 200, {"value": 1}

    async with observed_http_server(respond) as (url, requests):
        invalid = scenario("typed")
        if field == "payload":
            invalid.input_data["payload"] = value
        else:
            invalid.expected_output = value
        verification = IssueVerification(scenarios=[scenario("first"), invalid])
        with pytest.raises(ProtocolCanonicalizationError):
            await SandboxVerificationService().verify_sandbox(SimpleNamespace(id="typed", api_url=url), verification)
        assert not requests
        assert all(item.status == "pending" for item in verification.scenarios)


async def test_equivalent_json_value_is_admitted():
    async def respond(_request):
        return 200, {"value": 1}

    async with observed_http_server(respond) as (url, requests):
        verification = IssueVerification(scenarios=[scenario("json")])
        result = await SandboxVerificationService().verify_sandbox(SimpleNamespace(id="json", api_url=url), verification)
        assert result.passed == 1 and len(requests) == 1
        assert verification.scenarios[0].actual_output == {"value": 1}


@pytest.mark.parametrize("invalid_id", [None, 7])
async def test_invalid_scenario_shape_refuses_entire_batch_before_http(invalid_id):
    async def respond(_request):
        return 200, {"value": 1}

    async with observed_http_server(respond) as (url, requests):
        invalid = scenario("valid")
        invalid.id = invalid_id
        verification = IssueVerification(scenarios=[scenario("first"), invalid])
        with pytest.raises(ValidationError):
            await SandboxVerificationService().verify_sandbox(SimpleNamespace(id="sandbox", api_url=url), verification)
        assert not requests
        assert all(item.status == "pending" for item in verification.scenarios)
