from __future__ import annotations

from typing import Any

PROVIDER_TRUTH_TABLE_SCHEMA_VERSION = "1.0"

CAPABILITY_STATES = {"supported", "conditional", "unsupported", "unknown"}

_PROVIDER_TRUTH_ROWS: tuple[dict[str, Any], ...] = (
    {
        "provider": "ollama",
        "canonical_provider": "ollama",
        "capabilities": {
            "streaming": "supported",
            "json_mode": "conditional",
            "tools": "unsupported",
            "image_input": "unknown",
            "seed_control": "supported",
            "context_length_tokens": "unknown",
            "repair_tolerance": "supported",
        },
        "notes": [
            "streaming path is implemented by OllamaModelStreamProvider.",
            "json mode is attempted for strict JSON/task-class calls via format=json and can fail on older clients.",
            "tool call extraction is not implemented on the ollama local-model completion path.",
            "transient timeout/connection retry loop is enabled on completion requests.",
        ],
        "evidence_surfaces": [
            "orket/streaming/model_provider.py",
            "orket/adapters/llm/local_model_provider.py",
        ],
    },
    {
        "provider": "openai_compat",
        "canonical_provider": "openai_compat",
        "capabilities": {
            "streaming": "conditional",
            "json_mode": "conditional",
            "tools": "conditional",
            "image_input": "unknown",
            "seed_control": "supported",
            "context_length_tokens": "unknown",
            "repair_tolerance": "supported",
        },
        "notes": [
            "streaming support is runtime-gated by ORKET_MODEL_STREAM_OPENAI_USE_STREAM for model-stream workloads.",
            "json mode is runtime-gated by ORKET_LLM_OPENAI_RESPONSE_FORMAT values text|json_schema.",
            "tool call extraction is implemented when provider returns tool_calls payloads.",
            "transient timeout/connection retry loop is enabled on completion requests.",
        ],
        "evidence_surfaces": [
            "orket/streaming/model_provider.py",
            "orket/adapters/llm/local_model_provider.py",
        ],
    },
    {
        "provider": "lmstudio",
        "canonical_provider": "openai_compat",
        "capabilities": {
            "streaming": "conditional",
            "json_mode": "conditional",
            "tools": "conditional",
            "image_input": "unknown",
            "seed_control": "supported",
            "context_length_tokens": "unknown",
            "repair_tolerance": "supported",
        },
        "notes": [
            "lmstudio resolves through openai_compat request path with optional local CLI model auto-load.",
            "streaming/json/tools behavior inherits openai_compat runtime behavior.",
            "transient timeout/connection retry loop is enabled on completion requests.",
        ],
        "evidence_surfaces": [
            "orket/runtime/provider_runtime_target.py",
            "orket/streaming/model_provider.py",
            "orket/adapters/llm/local_model_provider.py",
        ],
    },
)


def provider_truth_table_snapshot() -> dict[str, object]:
    return {
        "schema_version": PROVIDER_TRUTH_TABLE_SCHEMA_VERSION,
        "providers": [dict(row) for row in _PROVIDER_TRUTH_ROWS],
    }


def validate_provider_truth_table() -> tuple[str, ...]:
    providers: list[str] = []
    for row in _PROVIDER_TRUTH_ROWS:
        provider = str(row.get("provider") or "").strip().lower()
        if not provider:
            raise ValueError("E_PROVIDER_TRUTH_PROVIDER_REQUIRED")
        providers.append(provider)
        capabilities = row.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ValueError(f"E_PROVIDER_TRUTH_CAPABILITIES_SCHEMA:{provider}")
        for capability_name, state in capabilities.items():
            if str(state or "").strip().lower() not in CAPABILITY_STATES:
                raise ValueError(f"E_PROVIDER_TRUTH_CAPABILITY_STATE:{provider}:{str(capability_name or '').strip()}")
    if len(set(providers)) != len(providers):
        raise ValueError("E_PROVIDER_TRUTH_DUPLICATE_PROVIDER")
    return tuple(sorted(providers))
