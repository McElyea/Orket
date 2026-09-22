"""Layer: contract. Explicit policy decisions depend only on detached supplied values."""

from dataclasses import FrozenInstanceError

import pytest

from orket.application.services import outbound_policy_input_service as inputs
from orket.core.contracts.outbound_policy import OutboundPolicyInputs, environment_policy_config
from orket.kernel.v1.outbound_policy_gate import apply_outbound_policy_gate

pytestmark = pytest.mark.contract


def test_equal_captured_policy_inputs_make_equal_decisions_without_environment(monkeypatch):
    config = {"pii_field_paths": ["private"], "allowed_output_fields": {"fixture": ["private", "keep"]}}
    first, second = (OutboundPolicyInputs.from_config(config) for _ in range(2))
    config["pii_field_paths"].clear()
    config["allowed_output_fields"]["fixture"].append("drop")

    def unexpected(*_args, **_kwargs):
        pytest.fail("explicit policy evaluation read an ambient environment")

    monkeypatch.setattr(inputs, "capture_kernel_environment", unexpected)
    payload = {"private": "fixture", "keep": "ok", "drop": "extra"}
    original = dict(payload)
    results = [
        apply_outbound_policy_gate(payload, {"surface": "fixture"}, policy_inputs=value) for value in (first, second)
    ]
    assert first == second and results[0] == results[1]
    assert results[0] == (
        {"private": "[REDACTED]", "keep": "ok"},
        {"applied": True, "redaction_count": 1, "redacted_paths": ["private"]},
    )
    assert payload == original
    with pytest.raises(FrozenInstanceError):
        first.placeholder = "changed"
    with pytest.raises(TypeError):
        first.allowed_output_fields["fixture"] = ()
    exported = first.to_config()
    exported["allowed_output_fields"].clear()
    assert first == second


@pytest.mark.parametrize(
    "config",
    [
        {"forbidden_patterns": ["["]},
        {"allowed_output_fields": []},
    ],
)
def test_invalid_normalized_policy_is_not_admitted(config):
    with pytest.raises(ValueError):
        OutboundPolicyInputs.from_config(config)


@pytest.mark.parametrize(
    "values",
    [
        {"pii_field_paths": "one"},
        {"forbidden_patterns": [object()]},
        {"allowed_output_fields": {1: ["one"]}},
        {"allowed_output_fields": {"one": "two"}},
        {"placeholder": []},
        {"sensitive_key_tokens": [1]},
    ],
)
def test_typed_inputs_refuse_non_value_members(values):
    with pytest.raises(TypeError):
        OutboundPolicyInputs(**values)


def test_explicit_empty_environment_and_config_overlay_preserve_merge_semantics(monkeypatch):
    monkeypatch.setenv("ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS", "ambient")
    base = inputs.capture_outbound_policy_inputs({"redact_paths": ["file"], "placeholder": "MASK"}, environment={})
    filtered, report = apply_outbound_policy_gate(
        {"file": "one", "request": "two", "ambient": "ok"}, {"pii_field_paths": ["request"]}, policy_inputs=base
    )
    assert filtered == {"file": "MASK", "request": "MASK", "ambient": "ok"}
    assert report["redacted_paths"] == ["file", "request"]
    assert environment_policy_config({"ORKET_OUTBOUND_POLICY_PII_FIELD_PATHS": '["a", "b"]'}) == {
        "pii_field_paths": ("a", "b")
    }
    with pytest.raises(TypeError, match="E_OUTBOUND_POLICY_INPUTS_REQUIRED"):
        apply_outbound_policy_gate({}, policy_inputs={})
