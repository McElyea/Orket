from __future__ import annotations

import pytest

from scripts.governance.build_architectural_truth_baseline import (
    _summarize_taxonomy,
    collect_api_factory_behavior,
    load_exception_register,
)


@pytest.mark.contract
def test_taxonomy_summary_preserves_collection_failure_and_conflicts() -> None:
    invalid = [{"nodeid": f"test_sample.py::test_case[{index}]", "layers": ["unit", "integration"]} for index in range(105)]
    payload = {
        "schema_version": "test_taxonomy_report.v2", "ok": False, "tests_total": 105,
        "missing_layer_total": 0, "invalid_layer_total": 105, "invalid_layers": invalid,
        "collection_exit_code": 2, "collection_errors": ["failed to import selected test module"],
        "classification_source": "pytest_collection",
    }
    summary = _summarize_taxonomy(payload)
    assert summary["ok"] is False
    assert summary["invalid_layer_total"] == 105
    assert summary["invalid_layers_sample"] == invalid[:100]
    assert summary["invalid_layers_omitted"] == 5
    assert summary["collection_exit_code"] == 2
    assert summary["collection_errors"] == payload["collection_errors"]
    assert summary["classification_source"] == "pytest_collection"


# Layer: contract
@pytest.mark.contract
def test_architectural_truth_exception_register_has_removal_authority() -> None:
    """Layer: contract. Verifies every recorded architecture exception has accountable removal metadata."""
    payload = load_exception_register()

    assert payload["valid"] is True
    assert payload["exceptions_total"] >= 15
    assert payload["invalid_ids"] == []
    for row in payload["exceptions"]:
        assert row["owner"] == "Orket Core"
        assert row["reason"]
        assert row["removal_condition"]
        assert row["evidence"]


@pytest.mark.integration
def test_architectural_truth_api_factory_probe_requires_real_isolation() -> None:
    """Layer: integration. The baseline passes API proof only for distinct retained owners."""
    payload = collect_api_factory_behavior()

    assert payload["result"] == "success"
    assert payload["same_app_object"] is False
    assert payload["first_context_replaced"] is False
    assert payload["distinct_contexts"] is True
    assert payload["distinct_engines"] is True
    assert payload["distinct_runtime_states"] is True
    assert payload["module_default_owner_absent"] is True
    assert payload["construction_deferred"] is True
    assert payload["health_statuses"] == [200, 200]
    assert payload["owners_closed"] is True
