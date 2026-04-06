from __future__ import annotations

from typing import Any

_CONFIG_OWNERSHIP_ROWS: tuple[dict[str, Any], ...] = (
    {
        "config_key": "ORKET_STATE_BACKEND_MODE",
        "owner": "orket/runtime/execution_pipeline.py",
        "domain": "state_backend",
    },
    {
        "config_key": "ORKET_RUN_LEDGER_MODE",
        "owner": "orket/runtime/execution_pipeline.py",
        "domain": "run_ledger",
    },
    {
        "config_key": "ORKET_ENABLE_GITEA_STATE_PILOT",
        "owner": "orket/runtime/execution_pipeline.py",
        "domain": "state_backend",
    },
    {
        "config_key": "ORKET_LLM_PROVIDER",
        "owner": "orket/adapters/llm/local_model_provider.py",
        "domain": "local_model_provider",
    },
    {
        "config_key": "ORKET_MODEL_PROVIDER",
        "owner": "orket/adapters/llm/local_model_provider.py",
        "domain": "local_model_provider",
    },
    {
        "config_key": "ORKET_MODEL_STREAM_REAL_PROVIDER",
        "owner": "orket/workloads/model_stream_v1.py",
        "domain": "model_stream_provider",
    },
    {
        "config_key": "ORKET_MODEL_STREAM_REAL_MODEL_ID",
        "owner": "orket/workloads/model_stream_v1.py",
        "domain": "model_stream_provider",
    },
    {
        "config_key": "ORKET_MODEL_STREAM_OPENAI_USE_STREAM",
        "owner": "orket/streaming/model_provider.py",
        "domain": "model_stream_provider",
    },
    {
        "config_key": "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL",
        "owner": "orket/runtime/provider_runtime_target.py",
        "domain": "provider_runtime_target",
    },
    {
        "config_key": "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL",
        "owner": "orket/runtime/provider_runtime_target.py",
        "domain": "provider_runtime_target",
    },
    {
        "config_key": "ORKET_PROVIDER_RUNTIME_TIMEOUT_SEC",
        "owner": "orket/runtime/provider_runtime_target.py",
        "domain": "provider_runtime_target",
    },
    {
        "config_key": "ORKET_PROVIDER_QUARANTINE",
        "owner": "orket/runtime/provider_quarantine_policy.py",
        "domain": "provider_quarantine",
    },
    {
        "config_key": "ORKET_PROVIDER_MODEL_QUARANTINE",
        "owner": "orket/runtime/provider_quarantine_policy.py",
        "domain": "provider_quarantine",
    },
    {
        "config_key": "ORKET_DETERMINISTIC_MODE",
        "owner": "orket/runtime/deterministic_mode_contract.py",
        "domain": "deterministic_mode",
    },
    {
        "config_key": "ORKET_PROTOCOL_DETERMINISTIC_MODE",
        "owner": "orket/runtime/deterministic_mode_contract.py",
        "domain": "deterministic_mode",
    },
)


def runtime_config_ownership_map_snapshot() -> dict[str, object]:
    rows = [dict(row) for row in _CONFIG_OWNERSHIP_ROWS]
    return {
        "schema_version": "1.0",
        "rows": rows,
    }


def validate_runtime_config_ownership_map() -> tuple[str, ...]:
    keys: list[str] = []
    for row in _CONFIG_OWNERSHIP_ROWS:
        key = str(row.get("config_key") or "").strip()
        owner = str(row.get("owner") or "").strip()
        domain = str(row.get("domain") or "").strip()
        if not key or not owner or not domain:
            raise ValueError("E_RUNTIME_CONFIG_OWNERSHIP_ROW_INVALID")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError("E_RUNTIME_CONFIG_OWNERSHIP_DUPLICATE_KEY")
    return tuple(sorted(keys))
