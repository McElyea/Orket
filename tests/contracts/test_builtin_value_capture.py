"""Layer: contract. one exact-builtins graph capture authority."""
from __future__ import annotations

import pytest

from orket.core.contracts.log_event_inputs import LOG_EVENT_INPUT_ERROR, capture_log_event_inputs
from orket.core.contracts.value_capture import capture_builtin_values
from tests.helpers.fixture_input_controls import HookedDict

pytestmark = pytest.mark.contract
ERROR = "E_FIXTURE_VERIFICATION_INPUT_UNSUPPORTED"


def test_generic_capture_detaches_aliases_and_preserves_builtin_categories():
    shared = {"values": [None, True, False, 7, -2, 1.5, "value"]}
    source = {"first": shared, "second": shared, "tuple": (1, {"nested": [2]})}
    captured = capture_builtin_values(source, error_code=ERROR)
    shared["values"].append("later")
    source["tuple"][1]["nested"].append(3)
    assert captured["first"] == captured["second"] == {"values": [None, True, False, 7, -2, 1.5, "value"]}
    assert captured["first"] is not shared and captured["second"] is not shared
    assert type(captured["tuple"]) is tuple and captured["tuple"] == (1, {"nested": [2]})
    captured["first"]["values"].append("owned edit")
    assert captured["second"]["values"][-1] == "value"


@pytest.mark.parametrize("kind", ["custom", "cycle", "nan", "infinity", "key", "deep"])
def test_generic_capture_uses_caller_error_and_log_wrapper_keeps_its_error(kind):
    custom, cycle = HookedDict(), []
    cycle.append(cycle)
    deep = []
    for _ in range(1500):
        deep = [deep]
    value = {"custom": custom, "cycle": cycle, "nan": float("nan"), "infinity": float("inf"),
             "key": {1: "bad"}, "deep": deep}[kind]
    with pytest.raises(TypeError) as generic:
        capture_builtin_values({"value": value}, error_code=ERROR)
    with pytest.raises(TypeError) as logging:
        capture_log_event_inputs("event", {"value": value})
    assert str(generic.value) == ERROR and str(logging.value) == LOG_EVENT_INPUT_ERROR
    assert custom.calls == []


@pytest.mark.parametrize("event,payload", [(3, {}), ("event", []), ("event", None)])
def test_log_wrapper_retains_its_root_contract(event, payload):
    with pytest.raises(TypeError) as failure:
        capture_log_event_inputs(event, payload)
    assert str(failure.value) == LOG_EVENT_INPUT_ERROR
