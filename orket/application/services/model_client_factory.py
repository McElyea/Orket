"""Application-owned construction over captured provider settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_model_factory import create_local_model_provider
from orket.application.services.process_input_service import capture_process_context
from orket.core.contracts.decision_inputs import ModelClientOptions


class AsyncModelClient:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def complete(self, messages: Any) -> Any:
        return await self.provider.complete(messages)

    async def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if callable(close):
            await close()


@dataclass(frozen=True)
class ModelClientFactory:
    environment: Mapping[str, str] = field(repr=False)
    cwd: Path | None = None

    def __post_init__(self) -> None:
        directory, captured = capture_process_context(cwd=self.cwd, environment=self.environment)
        object.__setattr__(self, "environment", captured)
        object.__setattr__(self, "cwd", directory)

    def create_provider(self, selected_model: str, options: ModelClientOptions) -> LocalModelProvider:
        return create_local_model_provider(
            model=selected_model, temperature=options.temperature, timeout=options.timeout,
            environment=self.environment, cwd=self.cwd
        )

    def create_client(self, provider: Any) -> AsyncModelClient:
        return AsyncModelClient(provider)
