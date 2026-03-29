from __future__ import annotations

from typing import Any


_ALLOWED_CLASSES = {"safe_transient", "dangerous_non_retryable"}
_ALLOWED_BACKOFF = {"none", "exponential"}
_SCHEMA_VERSION = "1.0"
_PROJECTION_SOURCE = "retry_classification_rules"

_RETRY_ROWS: tuple[dict[str, Any], ...] = (
    {
        "signal": "model_timeout_retry",
        "classification": "safe_transient",
        "max_attempts": 3,
        "backoff_strategy": "exponential",
        "terminal_behavior": "raise_model_timeout_error",
        "evidence_surfaces": [
            "orket/adapters/llm/local_model_provider.py::_complete_ollama",
            "orket/adapters/llm/local_model_provider.py::_complete_openai_compat",
        ],
    },
    {
        "signal": "model_connection_retry",
        "classification": "safe_transient",
        "max_attempts": 3,
        "backoff_strategy": "exponential",
        "terminal_behavior": "raise_model_connection_error",
        "evidence_surfaces": [
            "orket/adapters/llm/local_model_provider.py::_complete_ollama",
            "orket/adapters/llm/local_model_provider.py::_complete_openai_compat",
        ],
    },
    {
        "signal": "openai_http_status_error",
        "classification": "dangerous_non_retryable",
        "max_attempts": 1,
        "backoff_strategy": "none",
        "terminal_behavior": "raise_model_provider_error",
        "evidence_surfaces": [
            "orket/adapters/llm/local_model_provider.py::_complete_openai_compat",
        ],
    },
    {
        "signal": "unexpected_runtime_exception",
        "classification": "dangerous_non_retryable",
        "max_attempts": 1,
        "backoff_strategy": "none",
        "terminal_behavior": "raise_model_provider_error",
        "evidence_surfaces": [
            "orket/adapters/llm/local_model_provider.py::_complete_ollama",
            "orket/adapters/llm/local_model_provider.py::_complete_openai_compat",
        ],
    },
)


def retry_classification_policy_snapshot() -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "projection_only": True,
        "projection_source": _PROJECTION_SOURCE,
        "attempt_history_authoritative": False,
        "rows": [dict(row) for row in _RETRY_ROWS],
    }


def validate_retry_classification_policy(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    policy = dict(retry_classification_policy_snapshot() if payload is None else payload)
    if str(policy.get("schema_version") or "").strip() != _SCHEMA_VERSION:
        raise ValueError("E_RETRY_POLICY_SCHEMA_VERSION_INVALID")
    if policy.get("projection_only") is not True:
        raise ValueError("E_RETRY_POLICY_PROJECTION_ONLY_INVALID")
    if str(policy.get("projection_source") or "").strip() != _PROJECTION_SOURCE:
        raise ValueError("E_RETRY_POLICY_PROJECTION_SOURCE_INVALID")
    if policy.get("attempt_history_authoritative") is not False:
        raise ValueError("E_RETRY_POLICY_ATTEMPT_AUTHORITY_INVALID")
    rows = list(policy.get("rows") or [])
    if not rows:
        raise ValueError("E_RETRY_POLICY_EMPTY")

    signals: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_RETRY_POLICY_ROW_SCHEMA")
        signal = str(row.get("signal") or "").strip()
        classification = str(row.get("classification") or "").strip().lower()
        max_attempts = int(row.get("max_attempts") or 0)
        backoff = str(row.get("backoff_strategy") or "").strip().lower()
        terminal_behavior = str(row.get("terminal_behavior") or "").strip()
        evidence_surfaces = [str(token).strip() for token in row.get("evidence_surfaces", []) if str(token).strip()]

        if not signal or not terminal_behavior:
            raise ValueError("E_RETRY_POLICY_ROW_SCHEMA")
        if classification not in _ALLOWED_CLASSES:
            raise ValueError(f"E_RETRY_POLICY_CLASS_INVALID:{signal}")
        if backoff not in _ALLOWED_BACKOFF:
            raise ValueError(f"E_RETRY_POLICY_BACKOFF_INVALID:{signal}")
        if max_attempts < 1:
            raise ValueError(f"E_RETRY_POLICY_MAX_ATTEMPTS_INVALID:{signal}")
        if classification == "dangerous_non_retryable" and max_attempts != 1:
            raise ValueError(f"E_RETRY_POLICY_DANGEROUS_RETRY_COUNT:{signal}")
        if not evidence_surfaces:
            raise ValueError(f"E_RETRY_POLICY_EVIDENCE_REQUIRED:{signal}")
        signals.append(signal)

    if len(set(signals)) != len(signals):
        raise ValueError("E_RETRY_POLICY_DUPLICATE_SIGNAL")
    return tuple(sorted(signals))
