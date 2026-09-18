"""Explicit provider preparation inputs and the application admission port."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from orket.core.contracts.provider_runtime import ProviderRuntimeTarget, normalize_base_url, normalize_provider
from orket.exceptions import ModelConnectionError


@dataclass(frozen=True)
class ProviderPreparationRequest:
    provider: str
    requested_model: str
    base_url: str
    timeout_s: float
    api_key: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        normalize_provider(self.provider)
        object.__setattr__(self, "base_url", normalize_base_url(self.base_url, default=self.base_url))


class ProviderPreparationPort(Protocol):
    async def prepare(self, request: ProviderPreparationRequest) -> ProviderRuntimeTarget: ...


def require_prepared_target(request: ProviderPreparationRequest, target: ProviderRuntimeTarget) -> None:
    """A prepared observation must admit the same provider, request and endpoint."""
    if target.status != "OK" or not str(target.model_id or "").strip():
        available = ", ".join(target.available_models[:12]) or "(no models discovered)"
        raise ModelConnectionError(
            "Provider runtime target resolution failed "
            f"provider={target.requested_provider} requested_model={request.requested_model or '(unset)'} "
            f"resolution_mode={target.resolution_mode} available={available}"
        )
    if (target.requested_provider != request.provider
            or target.canonical_provider != normalize_provider(request.provider)
            or target.requested_model != request.requested_model
            or target.base_url.rstrip("/") != request.base_url.rstrip("/")):
        raise ModelConnectionError("E_PROVIDER_PREPARATION_TARGET_MISMATCH")
