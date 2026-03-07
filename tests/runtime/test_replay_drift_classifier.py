from __future__ import annotations

from orket.runtime.replay_drift_classifier import classify_replay_drift


# Layer: unit
def test_classify_replay_drift_returns_none_when_no_differences() -> None:
    report = classify_replay_drift(differences=[])
    assert report["drift_schema_version"] == "1.0"
    assert report["drift_detected"] is False
    assert report["primary_layer"] == "none"
    assert report["detected_layers"] == []
    assert report["layer_reasons"] == []
    assert report["unclassified_fields"] == []


# Layer: unit
def test_classify_replay_drift_prioritizes_runtime_contract_layer() -> None:
    report = classify_replay_drift(
        differences=[
            {"field": "artifact_inventory", "a": [], "b": [{"path": "a.txt"}]},
            {"field": "runtime_policy_versions", "a": {"retry_policy": "1.0"}, "b": {"retry_policy": "2.0"}},
            {"field": "operations", "a": {"op-1": {"ok": True}}, "b": {"op-1": {"ok": False}}},
        ]
    )
    assert report["drift_detected"] is True
    assert report["primary_layer"] == "runtime_contract_drift"
    assert report["detected_layers"] == [
        "runtime_contract_drift",
        "tool_behavior_drift",
        "artifact_formatting_drift",
    ]


# Layer: unit
def test_classify_replay_drift_classifies_compatibility_tool_schema_fields() -> None:
    report = classify_replay_drift(
        differences=[
            {
                "field": "compatibility_validation",
                "a": {
                    "missing_contract_fields": ["tool_registry_version"],
                    "mismatch_fields": [],
                    "lifecycle_missing": [],
                },
                "b": {
                    "missing_contract_fields": [],
                    "mismatch_fields": [],
                    "lifecycle_missing": [],
                },
            }
        ]
    )
    assert report["primary_layer"] == "tool_schema_drift"
    assert report["detected_layers"] == ["tool_schema_drift"]
    assert report["layer_reasons"] == [
        {"layer": "tool_schema_drift", "fields": ["compatibility_validation.tool_registry_version"]}
    ]


# Layer: unit
def test_classify_replay_drift_prioritizes_prompt_over_behavior_and_artifacts() -> None:
    report = classify_replay_drift(
        differences=[
            {"field": "operations", "a": {"op-1": {"ok": True}}, "b": {"op-1": {"ok": False}}},
            {"field": "artifact_inventory", "a": [], "b": [{"path": "a.txt"}]},
            {"field": "prompt_hash", "a": "aaa", "b": "bbb"},
        ]
    )
    assert report["primary_layer"] == "prompt_drift"
    assert report["detected_layers"] == [
        "prompt_drift",
        "tool_behavior_drift",
        "artifact_formatting_drift",
    ]


# Layer: unit
def test_classify_replay_drift_falls_back_unknown_fields_to_tool_behavior() -> None:
    report = classify_replay_drift(
        differences=[
            {"field": "unknown_field", "a": "left", "b": "right"},
        ]
    )
    assert report["primary_layer"] == "tool_behavior_drift"
    assert report["detected_layers"] == ["tool_behavior_drift"]
    assert report["unclassified_fields"] == ["unknown_field"]
