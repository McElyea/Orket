"""Immutable API facts and strict recommendations; no runtime effect claim."""
import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from orket.application.services.api_policy_input_service import (
    admit_api_bool,
    capture_api_invocation,
    capture_preview_target,
    normalize_api_metrics,
    normalize_archive_result,
    order_explorer_items,
    recommend_websocket_removal,
)
from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket_extension_sdk import FrozenJson

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("case", json.loads((Path(__file__).parents[1] / "fixtures/api_policy_v049.json").read_text())["cases"])
def test_published_default_outcomes(case):
    args = list(case["args"])
    method = case["method"]
    if method == "normalize_metrics":
        args[0] = FrozenJson.freeze(args[0])
    elif method == "sort_explorer_items":
        args[0] = tuple(MappingProxyType(item) for item in args[0])
    elif method == "resolve_preview_invocation":
        args[0] = MappingProxyType(args[0])
    elif method == "has_archive_selector":
        args[0], args[2] = [None if value is None else tuple(value) for value in (args[0], args[2])]
    elif method == "normalize_archive_response":
        args[0], args[1] = tuple(args[0]), tuple(args[1])
    assert getattr(DefaultApiRuntimeStrategyNode(), method)(*args) == case["result"]


@pytest.mark.parametrize("value", [None, 1, "true", [], {}])
def test_non_boolean_recommendation_is_refused(value):
    with pytest.raises(ValueError, match="INVALID_BOOLEAN"):
        admit_api_bool(value)


@pytest.mark.parametrize("payload", [None, {}, {"method_name": 1}, {"method_name": "run", "args": "x"},
    {"method_name": "run", "kwargs": {1: "x"}}, {"method_name": "run", "extra": True},
    {"method_name": "run", "unsupported_detail": None}])
def test_invalid_invocation_shape_is_refused(payload):
    with pytest.raises(ValueError, match="E_API_POLICY_INVALID"):
        capture_api_invocation(payload)


def test_invocation_detaches_nested_arguments():
    proposal = {"method_name": "run", "args": [{"items": ["admitted"]}], "kwargs": {"options": {"a": 1}}}
    captured = capture_api_invocation(proposal)
    proposal["args"][0]["items"].append("replacement")
    proposal["kwargs"]["options"]["a"] = 2
    assert captured == {"method_name": "run", "args": [{"items": ["admitted"]}], "kwargs": {"options": {"a": 1}}}


def test_metrics_are_immutable_detached_observations():
    observed = {"cpu_percent": 12, "nested": {"values": [1]}}
    def normalize(inputs):
        assert isinstance(inputs, FrozenJson)
        private = inputs.thaw()
        private["nested"]["values"].append(2)
        return private
    result = normalize_api_metrics(SimpleNamespace(normalize_metrics=normalize), observed)
    assert observed == {"cpu_percent": 12, "nested": {"values": [1]}}
    assert result["nested"]["values"] == [1, 2]


def test_preview_target_does_not_borrow_proposal_mapping():
    proposal = {"mode": "rock", "asset_name": "requested", "department": "core"}
    captured = capture_preview_target(proposal)
    proposal["asset_name"] = "replacement"
    assert captured["asset_name"] == "requested"
    with pytest.raises(TypeError):
        captured["asset_name"] = "mutated"


@pytest.mark.parametrize("replacement", [[], [{"name": "invented", "ext": ".txt", "is_dir": False}],
    [{"name": "observed", "ext": ".txt", "is_dir": 0}]])
def test_explorer_recommendation_cannot_rewrite_observed_facts(replacement):
    node = SimpleNamespace(sort_explorer_items=lambda inputs: replacement)
    with pytest.raises(ValueError, match="E_API_POLICY_"):
        order_explorer_items(node, [{"name": "observed", "ext": ".txt", "is_dir": False}])


def test_archive_custom_fields_and_order_preserve_observed_claims():
    class Custom(DefaultApiRuntimeStrategyNode):
        def normalize_archive_response(self, archived_ids, missing_ids, archived_count):
            assert type(archived_ids) is tuple and type(missing_ids) is tuple
            result = super().normalize_archive_response(archived_ids, missing_ids, archived_count)
            result["archived_ids"].reverse()
            return dict(result, policy="custom")
    assert normalize_archive_result(Custom(), ["B", "A", "A"], ["Z", "Z"], 2) == {
        "ok": True, "archived_count": 4, "archived_ids": ["B", "A"], "missing_ids": ["Z"], "policy": "custom"}


@pytest.mark.parametrize("field,value", [("ok", False), ("archived_count", True), ("archived_count", 999),
    ("archived_ids", ["A", "A"]), ("missing_ids", ["invented"])])
def test_archive_contradictory_reserved_fields_are_refused(field, value):
    proposal = dict(ok=True, archived_count=1, archived_ids=["A"], missing_ids=[])
    proposal[field] = value
    node = SimpleNamespace(normalize_archive_response=lambda **kwargs: proposal)
    with pytest.raises(ValueError, match="E_API_ARCHIVE_RESULT_CONTRADICTION"):
        normalize_archive_result(node, ["A"], [], 0)


@pytest.mark.parametrize("error,expected", [(RuntimeError("x"), "runtime_error"), (ValueError("x"), "value_error"),
    (KeyError("x"), "other")])
def test_websocket_policy_observes_scalar_category(error, expected):
    seen = []
    def decide(category):
        seen.append(category)
        return category != "other"
    assert recommend_websocket_removal(SimpleNamespace(should_remove_websocket=decide), error) == (expected != "other")
    assert seen == [expected]
