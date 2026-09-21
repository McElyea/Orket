"""Model family defaults consume explicit configuration; environment decoding is separate."""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from orket.agents.model_family_registry import ModelFamilyRegistry
from orket.core.contracts.eos_calendar import EosSprintBaseline

pytestmark = pytest.mark.contract
PUBLISHED = json.loads((Path(__file__).parents[1] / "fixtures/runtime_observations_v051.json").read_text())["cases"]


def test_none_configuration_does_not_read_environment(monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_FAMILY_PATTERNS", '{"probe":"admitted"}')
    match = ModelFamilyRegistry.from_config().resolve("probe-model")
    assert (match.family, match.recognized) == ("generic", False)


@pytest.mark.parametrize("raw", ['{"broken":', "not-json", "["])
def test_malformed_environment_json_is_refused(raw):
    with pytest.raises(ValueError, match="E_MODEL_FAMILY_PATTERNS_JSON"):
        ModelFamilyRegistry.from_environment({"ORKET_MODEL_FAMILY_PATTERNS": raw})


def test_empty_environment_and_captured_pattern_values(monkeypatch):
    monkeypatch.setenv("ORKET_MODEL_FAMILY_PATTERNS", '{"probe":"ambient"}')
    assert ModelFamilyRegistry.from_environment({}).resolve("probe-model").family == "generic"
    environment = {"ORKET_MODEL_FAMILY_PATTERNS": '{"probe":"admitted"}'}
    registry = ModelFamilyRegistry.from_environment(environment)
    environment["ORKET_MODEL_FAMILY_PATTERNS"] = '{"probe":"replacement"}'
    assert registry.resolve("probe-model").family == "admitted"


@pytest.mark.parametrize("case", PUBLISHED)
def test_supported_observations_match_published_v051(case):
    if case["kind"] == "model_family":
        match = ModelFamilyRegistry.from_config(case["config"]).resolve(case["name"])
        assert {"family": match.family, "recognized": match.recognized} == case["result"]
    else:
        calendar = EosSprintBaseline.from_environment(case["environment"])
        if isinstance(case["result"], dict):
            error = {"TypeError": TypeError, "ValueError": ValueError}[case["result"]["error"]]
            with pytest.raises(error, match=re.escape(case["result"]["message"])):
                calendar.current_sprint(datetime.fromisoformat(case["stamp"]))
        else:
            assert calendar.current_sprint(datetime.fromisoformat(case["stamp"])) == case["result"]
