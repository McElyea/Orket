from __future__ import annotations

from typing import Any

_RUNTIME_POLICY_VERSIONS = {
    "prompt_budget_policy": "1.0",
    "retry_policy": "1.1",
    "promotion_gate_policy": "1.0",
}


def runtime_policy_versions_snapshot() -> dict[str, Any]:
    return dict(_RUNTIME_POLICY_VERSIONS)
