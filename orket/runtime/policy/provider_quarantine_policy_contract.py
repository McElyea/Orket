from __future__ import annotations

from typing import Any

PROVIDER_QUARANTINE_POLICY_CONTRACT_SCHEMA_VERSION = "1.0"

_EXPECTED_ENV_KEYS = (
    "ORKET_PROVIDER_MODEL_QUARANTINE",
    "ORKET_PROVIDER_QUARANTINE",
)


def provider_quarantine_policy_contract_snapshot() -> dict[str, Any]:
    return {
        "schema_version": PROVIDER_QUARANTINE_POLICY_CONTRACT_SCHEMA_VERSION,
        "env_keys": list(_EXPECTED_ENV_KEYS),
        "provider_separator": ",",
        "provider_model_separator": ":",
        "policy_targets": [
            "requested_provider",
            "canonical_provider",
            "model_id",
        ],
        "default_policy": {
            "providers": [],
            "provider_models": [],
        },
    }


def validate_provider_quarantine_policy_contract(
    payload: dict[str, Any] | None = None,
) -> tuple[str, ...]:
    contract = dict(payload or provider_quarantine_policy_contract_snapshot())

    env_keys = [str(token).strip() for token in contract.get("env_keys", []) if str(token).strip()]
    if not env_keys:
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_ENV_KEYS_EMPTY")
    if len(set(env_keys)) != len(env_keys):
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_ENV_KEYS_DUPLICATE")
    if tuple(sorted(env_keys)) != tuple(sorted(_EXPECTED_ENV_KEYS)):
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_ENV_KEYS_MISMATCH")

    provider_separator = str(contract.get("provider_separator") or "").strip()
    provider_model_separator = str(contract.get("provider_model_separator") or "").strip()
    if provider_separator != ",":
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_PROVIDER_SEPARATOR_INVALID")
    if provider_model_separator != ":":
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_PROVIDER_MODEL_SEPARATOR_INVALID")

    policy_targets = [str(token).strip() for token in contract.get("policy_targets", []) if str(token).strip()]
    if tuple(policy_targets) != ("requested_provider", "canonical_provider", "model_id"):
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_TARGETS_MISMATCH")

    default_policy = contract.get("default_policy")
    if not isinstance(default_policy, dict):
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_DEFAULT_POLICY_SCHEMA")
    default_providers = list(default_policy.get("providers") or [])
    default_provider_models = list(default_policy.get("provider_models") or [])
    if default_providers or default_provider_models:
        raise ValueError("E_PROVIDER_QUARANTINE_POLICY_CONTRACT_DEFAULT_POLICY_NON_EMPTY")

    return tuple(sorted(env_keys))
