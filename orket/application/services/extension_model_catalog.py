"""Application-owned model inventory over a captured provider environment."""
from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

import httpx

from orket.application.services.api_event_service import ApiEventService
from orket.core.contracts.provider_runtime import provider_from_environment
from orket.runtime.config.provider_runtime_target import list_provider_models
from orket.services.extension_memory_namespace import validate_extension_id


class ExtensionModelCatalogUnavailable(RuntimeError):
    def __init__(self, extension_id: str, provider: str) -> None:
        self.extension_id = extension_id
        self.provider = provider
        super().__init__(f"Extension runtime model catalog unavailable for provider '{provider}' "
                         f"and extension '{extension_id}'.")

    def detail(self) -> dict[str, Any]:
        return {"ok": False, "code": "E_EXTENSION_RUNTIME_MODEL_CATALOG_UNAVAILABLE",
                "message": str(self), "requested_provider": self.provider,
                "extension_id": self.extension_id, "degraded": True}


class ExtensionModelCatalog:
    def __init__(self, *, environment: Mapping[str, str], events: ApiEventService) -> None:
        self._environment = MappingProxyType(dict(environment))
        self._events = events

    async def list_models(self, *, extension_id: str, provider: str = "") -> dict[str, Any]:
        validated_id = validate_extension_id(extension_id)
        environment, events = self._environment, self._events
        requested = str(provider or "").strip().lower() or provider_from_environment(environment)
        try:
            payload = await list_provider_models(
                provider=requested, base_url=None, timeout_s=8.0, api_key=None, environment=environment,
            )
        except (httpx.HTTPError, OSError, RuntimeError, TypeError) as exc:
            await events.emit("extension_runtime_model_catalog_unavailable", {
                "extension_id": validated_id, "provider": requested, "error": str(exc),
            })
            raise ExtensionModelCatalogUnavailable(validated_id, requested) from exc
        raw_models = payload.get("models")
        models = [str(model).strip() for model in raw_models if str(model).strip()] if isinstance(raw_models, list) else []
        default_model = "Command-R:35B" if requested == "ollama" else ""
        if default_model not in models and models:
            default_model = models[0]
        return {
            "ok": True, "extension_id": validated_id,
            "requested_provider": str(payload.get("requested_provider") or requested),
            "canonical_provider": str(payload.get("canonical_provider") or requested),
            "base_url": str(payload.get("base_url") or ""), "models": models, "default_model": default_model,
        }
