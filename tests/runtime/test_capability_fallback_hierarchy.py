from __future__ import annotations

import pytest

from orket.runtime.capability_fallback_hierarchy import (
    capability_fallback_hierarchy_snapshot,
    validate_capability_fallback_hierarchy,
)


# Layer: unit
def test_capability_fallback_hierarchy_snapshot_contains_streaming_hierarchy() -> None:
    payload = capability_fallback_hierarchy_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["fallback_hierarchy"]["streaming"][0]["provider"] == "ollama"


# Layer: contract
def test_validate_capability_fallback_hierarchy_accepts_current_snapshot() -> None:
    payload = validate_capability_fallback_hierarchy()
    assert "tools" in payload["fallback_hierarchy"]


# Layer: contract
def test_validate_capability_fallback_hierarchy_rejects_state_drift() -> None:
    payload = capability_fallback_hierarchy_snapshot()
    payload["fallback_hierarchy"]["streaming"][0]["state"] = "unsupported"
    with pytest.raises(ValueError, match="E_CAPABILITY_FALLBACK_STATE_DRIFT:streaming:ollama"):
        _ = validate_capability_fallback_hierarchy(payload)
