from __future__ import annotations

import pytest

from scripts.governance.build_architectural_truth_baseline import (
    collect_api_factory_behavior,
    load_exception_register,
)


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
