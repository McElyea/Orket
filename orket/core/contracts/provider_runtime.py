"""Pure provider identity and captured runtime-target values."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, cast

from orket.core.contracts.protocol_hashing import canonical_json
from orket_extension_sdk import FrozenJson

DEFAULT_LOCAL_PROVIDER = "llama_cpp"
DEFAULT_LOCAL_MODEL = "orcarouter_qwen3.8-27b-uncensored-q4_k_l"
PROVIDER_CHOICES = (DEFAULT_LOCAL_PROVIDER, "lmstudio", "ollama", "openai_compat")


def provider_from_environment(environment: Mapping[str, str], *keys: str) -> str:
    """Resolve supplied values only; observing the process environment is the caller's effect."""
    for key in keys or ("ORKET_LLM_PROVIDER", "ORKET_MODEL_PROVIDER"):
        value = str(environment.get(key) or "").strip().lower()
        if value:
            return value
    return DEFAULT_LOCAL_PROVIDER


def effective_provider(provider: str | None, *, default: str = DEFAULT_LOCAL_PROVIDER) -> str:
    requested = str(provider or "").strip().lower() or str(default or "").strip().lower() or DEFAULT_LOCAL_PROVIDER
    return requested if requested in PROVIDER_CHOICES else requested


def normalize_provider(provider: str) -> str:
    raw = effective_provider(provider)
    if raw not in PROVIDER_CHOICES:
        raise ValueError(f"E_UNKNOWN_PROVIDER_INPUT:{raw}")
    return "ollama" if raw == "ollama" else "openai_compat"


@dataclass(frozen=True)
class ProviderRuntimeTarget:
    requested_provider: str
    canonical_provider: str
    requested_model: str
    model_id: str
    base_url: str
    resolution_mode: str
    inventory_source: str
    available_models: tuple[str, ...]
    loaded_models_before: tuple[str, ...]
    loaded_models_after: tuple[str, ...]
    auto_load_attempted: bool
    auto_load_performed: bool
    status: str
    gguf_model_root: str = ""
    gguf_inventory_status: str = "not_applicable"
    gguf_models: tuple[dict[str, Any] | FrozenJson, ...] = ()

    def __post_init__(self):
        for name in ("available_models", "loaded_models_before", "loaded_models_after"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        records = tuple(FrozenJson(canonical_json(row.thaw() if isinstance(row, FrozenJson) else row))
                        for row in self.gguf_models)
        object.__setattr__(self, "gguf_models", records)

    def to_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["gguf_models"] = tuple(cast(FrozenJson, row).thaw() for row in self.gguf_models)
        return payload
