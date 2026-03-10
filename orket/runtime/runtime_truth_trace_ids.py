from __future__ import annotations


RUNTIME_TRUTH_TRACE_IDS_SCHEMA_VERSION = "1.0"

_TRACE_IDS: dict[str, str] = {
    "run_phase_contract": "TRUTH-A-RUN-PHASE-CONTRACT",
    "runtime_status_vocabulary": "TRUTH-A-DEGRADATION-VOCABULARY",
    "degradation_taxonomy": "TRUTH-A-DEGRADATION-TAXONOMY",
    "fail_behavior_registry": "TRUTH-A-FAIL-BEHAVIOR-REGISTRY",
    "provider_truth_table": "TRUTH-A-PROVIDER-TRUTH-TABLE",
    "state_transition_registry": "TRUTH-A-STATE-TRANSITION-REGISTRY",
    "timeout_semantics_contract": "TRUTH-A-TIMEOUT-SEMANTICS-CONTRACT",
    "streaming_semantics_contract": "TRUTH-A-STREAMING-SEMANTICS-CONTRACT",
    "runtime_truth_contract_drift_report": "TRUTH-W2A-CONTRACT-DRIFT-CHECKER",
    "runtime_invariant_registry": "TRUTH-W2A-INVARIANT-REGISTRY",
    "runtime_config_ownership_map": "TRUTH-W2A-CONFIG-OWNERSHIP-MAP",
    "unknown_input_policy": "TRUTH-W2A-UNKNOWN-INPUT-POLICY",
    "clock_time_authority_policy": "TRUTH-W2A-CLOCK-TIME-AUTHORITY-POLICY",
    "deterministic_mode_contract": "TRUTH-B-DETERMINISTIC-MODE-FLAG",
    "route_decision_artifact": "TRUTH-B-ROUTE-DECISION-ARTIFACT",
}


def runtime_truth_trace_ids_snapshot() -> dict[str, object]:
    rows = [
        {
            "artifact": artifact,
            "trace_id": trace_id,
        }
        for artifact, trace_id in sorted(_TRACE_IDS.items())
    ]
    return {
        "schema_version": RUNTIME_TRUTH_TRACE_IDS_SCHEMA_VERSION,
        "trace_ids": rows,
    }


def resolve_runtime_truth_trace_id(artifact: str) -> str:
    key = str(artifact or "").strip()
    token = _TRACE_IDS.get(key)
    if token is None:
        raise ValueError(f"E_RUNTIME_TRUTH_TRACE_ID_UNKNOWN:{key or '<empty>'}")
    return token
