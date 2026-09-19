"""Pure comparison of explicit observed protocol snapshots, with evidence admission."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_COMPARED_FIELDS = (
    "status", "failure_class", "failure_reason", "last_event_seq", "ledger_schema_version",
    "runtime_contract_hash", "runtime_policy_versions", "compatibility_validation",
    "operations", "artifact_inventory", "receipt_inventory",
)


def compare_protocol_snapshots(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    differences = [{"field": name, "a": left[name], "b": right[name]}
                   for name in _COMPARED_FIELDS if left[name] != right[name]]
    count_a, count_b = int(left["event_count"]), int(right["event_count"])
    available = count_a > 0 and count_b > 0
    matched = available and left["state_digest"] == right["state_digest"] and not differences
    status = ("matched" if matched else "mismatched") if available else "insufficient_evidence"
    return {"deterministic_match": bool(matched), "state_digest_a": left["state_digest"],
            "state_digest_b": right["state_digest"], "differences": differences,
            "comparison_status": status, "comparison_scope": "observed_protocol_state",
            "event_count_a": count_a, "event_count_b": count_b}
