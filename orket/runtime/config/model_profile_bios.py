from __future__ import annotations

from typing import Any

from orket.runtime.provider_truth_table import provider_truth_table_snapshot


def _provider_rows() -> list[dict[str, Any]]:
    providers = provider_truth_table_snapshot().get("providers")
    if not isinstance(providers, list):
        return []
    return [dict(row) for row in providers if isinstance(row, dict)]


def _repair_tolerance_for_provider(provider: str) -> str:
    for row in _provider_rows():
        if str(row.get("provider") or "").strip().lower() != provider:
            continue
        capabilities_payload = row.get("capabilities")
        capabilities = capabilities_payload if isinstance(capabilities_payload, dict) else {}
        return str(capabilities.get("repair_tolerance") or "unknown").strip().lower()
    return "unknown"


def model_profile_bios_snapshot() -> dict[str, Any]:
    profiles = [
        {
            "provider": "ollama",
            "profile_id": "ollama-default",
            "strictness_profile": "medium",
            "repair_tolerance": _repair_tolerance_for_provider("ollama"),
            "hazard_flags": [],
        },
        {
            "provider": "openai_compat",
            "profile_id": "openai-compat-default",
            "strictness_profile": "high",
            "repair_tolerance": _repair_tolerance_for_provider("openai_compat"),
            "hazard_flags": ["response_shape_variation"],
        },
        {
            "provider": "lmstudio",
            "profile_id": "lmstudio-default",
            "strictness_profile": "high",
            "repair_tolerance": _repair_tolerance_for_provider("lmstudio"),
            "hazard_flags": ["session_mode_mismatch"],
        },
    ]
    return {
        "schema_version": "1.0",
        "profiles": profiles,
    }


def validate_model_profile_bios(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    bios = dict(payload or model_profile_bios_snapshot())
    profiles_payload = bios.get("profiles")
    rows = profiles_payload if isinstance(profiles_payload, list) else []
    if not rows:
        raise ValueError("E_MODEL_PROFILE_BIOS_EMPTY")

    truth_rows = _provider_rows()
    truth_providers = {
        str(row.get("provider") or "").strip().lower() for row in truth_rows if str(row.get("provider") or "").strip()
    }
    allowed_strictness = {"low", "medium", "high"}
    profile_ids: list[str] = []
    observed_providers: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_MODEL_PROFILE_BIOS_ROW_SCHEMA")
        provider = str(row.get("provider") or "").strip().lower()
        profile_id = str(row.get("profile_id") or "").strip()
        strictness = str(row.get("strictness_profile") or "").strip().lower()
        repair_tolerance = str(row.get("repair_tolerance") or "").strip().lower()
        if provider not in truth_providers:
            raise ValueError(f"E_MODEL_PROFILE_BIOS_PROVIDER_UNKNOWN:{provider or '<empty>'}")
        if not profile_id:
            raise ValueError(f"E_MODEL_PROFILE_BIOS_PROFILE_ID_REQUIRED:{provider}")
        if strictness not in allowed_strictness:
            raise ValueError(f"E_MODEL_PROFILE_BIOS_STRICTNESS_INVALID:{provider}")
        if repair_tolerance not in {"supported", "conditional", "unsupported", "unknown"}:
            raise ValueError(f"E_MODEL_PROFILE_BIOS_REPAIR_TOLERANCE_INVALID:{provider}")
        profile_ids.append(profile_id)
        observed_providers.add(provider)
    if len(set(profile_ids)) != len(profile_ids):
        raise ValueError("E_MODEL_PROFILE_BIOS_DUPLICATE_PROFILE_ID")
    if observed_providers != truth_providers:
        raise ValueError("E_MODEL_PROFILE_BIOS_PROVIDER_SET_MISMATCH")
    return tuple(sorted(profile_ids))
