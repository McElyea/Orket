"""Contract classification of supplied differences, not replay execution."""
from copy import deepcopy

import pytest

from orket.runtime.evidence.replay_drift_classifier import classify_replay_drift

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("surface,layer", [
    ("runtime_contract_hash", "runtime_contract_drift"),
    ("runtime_policy_versions.retry", "runtime_contract_drift"),
    ("capability_manifest.tools", "tool_schema_drift"),
    ("workspace_state_snapshot.workspace_hash", "artifact_formatting_drift"),
    ("unknown.surface", "runtime_contract_drift"),
])
def test_structured_compatibility_causes_keep_their_layer_and_exact_field(surface, layer):
    differences = [{"field": "compatibility_validation", "a": {"mismatch_fields": [surface, " "]},
                    "b": {"missing_contract_fields": [surface]}}]
    before = deepcopy(differences)
    report = classify_replay_drift(differences=differences)
    assert report["detected_layers"] == [layer] and report["primary_layer"] == layer
    assert report["layer_reasons"] == [{"layer": layer, "fields": ["compatibility_validation." + surface]}]
    assert report["unclassified_fields"] == [] and differences == before


@pytest.mark.parametrize("payload,field", [
    (None, "compatibility_validation"),
    ({"mismatch_fields": "invalid"}, "compatibility_validation"),
    ({"lifecycle_missing": ["run_finalized"]}, "compatibility_validation.lifecycle_missing"),
])
def test_unstructured_or_missing_lifecycle_evidence_stays_runtime_drift(payload, field):
    report = classify_replay_drift(differences=[{"field": "compatibility_validation", "a": payload}])
    assert report["primary_layer"] == "runtime_contract_drift"
    assert report["layer_reasons"] == [{"layer": "runtime_contract_drift", "fields": [field]}]


def test_unknown_fields_remain_visible_without_overriding_known_precedence():
    report = classify_replay_drift(differences=[{"field": " "}, {"field": "tool_schema_hash"},
                                              {"field": "future-field"}, {"field": "future-field"}])
    assert report["primary_layer"] == "tool_schema_drift"
    assert report["detected_layers"] == ["tool_schema_drift"]
    assert report["unclassified_fields"] == ["future-field"]
