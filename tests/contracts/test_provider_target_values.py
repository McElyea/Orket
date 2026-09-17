"""Layer: contract. Provider metadata must retain its captured nested values."""
from dataclasses import FrozenInstanceError

import pytest

from orket.core.contracts.protocol_hashing import ProtocolCanonicalizationError
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget

pytestmark = pytest.mark.contract


def _target(record):
    return ProviderRuntimeTarget(requested_provider="llama_cpp", canonical_provider="openai_compat",
        requested_model="fixture", model_id="fixture", base_url="http://127.0.0.1:8080/v1",
        resolution_mode="requested", inventory_source="http_models+gguf_inventory",
        available_models=("fixture",), loaded_models_before=(), loaded_models_after=(),
        auto_load_attempted=False, auto_load_performed=False, status="OK", gguf_models=(record,))


def test_provider_target_captures_nested_inventory_values():
    record = {"alias": "fixture", "metadata": {"digest_status": "pending"}}
    target = _target(record)
    before = target.to_payload()
    record["metadata"]["digest_status"] = "computed"
    assert target.to_payload() == before


def test_provider_target_export_does_not_alias_captured_values():
    target = _target({"alias": "fixture", "metadata": {"digest_status": "pending"}})
    output = target.to_payload()
    output["gguf_models"][0]["metadata"]["digest_status"] = "computed"
    assert target.to_payload()["gguf_models"][0]["metadata"]["digest_status"] == "pending"


def test_captured_inventory_cannot_be_mutated_in_place():
    target = _target({"alias": "fixture"})
    with pytest.raises(FrozenInstanceError):
        target.gguf_models[0].canonical = "{}"


def test_target_refuses_non_json_metadata_without_stringifying_it():
    class EffectfulValue:
        def __str__(self):
            pytest.fail("Arbitrary input conversion is not a provider observation")

    with pytest.raises(ProtocolCanonicalizationError):
        _target({"alias": EffectfulValue()})
