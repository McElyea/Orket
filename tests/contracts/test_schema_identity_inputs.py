"""Core schema values validate explicit identity and have no warning effects."""
from __future__ import annotations

import warnings

import pytest
from pydantic import ValidationError

from orket.schema import (
    BaseCardConfig,
    CardDetail,
    EnvironmentConfig,
    EpicConfig,
    IssueConfig,
    RockConfig,
    RoleConfig,
    VerificationScenario,
)

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("model,payload", [
    (BaseCardConfig, {"summary": "Card"}),
    (IssueConfig, {"summary": "Issue"}),
    (EpicConfig, {"summary": "Epic", "team": "team", "environment": "dev"}),
    (RockConfig, {"summary": "Rock", "epics": []}),
    (RoleConfig, {"summary": "Role", "description": "Build"}),
    (CardDetail, {"summary": "Tree"}),
    (VerificationScenario, {"description": "Check", "input_data": {}, "expected_output": True}),
])
def test_core_requires_identity_and_preserves_complete_value_parity(model, payload):
    with pytest.raises(ValidationError) as failure:
        model.model_validate(payload)
    assert any(error["loc"] == ("id",) and error["type"] == "missing" for error in failure.value.errors())
    complete = {"id": "retained", **payload}
    first, second = model.model_validate(complete), model.model_validate(complete)
    assert first.id == "retained"
    assert first.model_dump() == second.model_dump()


def test_unknown_environment_keys_are_rejected_without_warning_effects():
    with warnings.catch_warnings(record=True) as observations, pytest.raises(
        ValidationError, match="Extra inputs are not permitted"
    ):
        EnvironmentConfig(name="dev", model="model", obsolete=True)
    assert observations == []


def test_known_environment_values_keep_deterministic_parity():
    payload = {"name": "dev", "model": "model", "params": {"provider_option": True}}
    assert EnvironmentConfig.model_validate(payload).model_dump() == EnvironmentConfig.model_validate(payload).model_dump()
