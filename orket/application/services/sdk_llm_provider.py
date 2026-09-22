from __future__ import annotations

from collections.abc import Mapping

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.execution.sync_coroutine_owner import SyncCoroutineOwner
from orket.application.services.local_model_factory import create_local_model_provider
from orket.capabilities.sync_bridge import run_coro_sync
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse, nonnegative_int_or_none


class LocalModelCapabilityProvider:
    """Application-owned SDK model composition; async callers must offload and drain it."""

    def __init__(
        self,
        *,
        model: str,
        temperature: float,
        seed: int | None,
        timeout: int = 300,
        provider: str = "",
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self._provider = create_local_model_provider(
            model=model,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
            provider=provider,
            environment=environment,
        )
        self._coroutines = SyncCoroutineOwner()
        self._closed = False

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        require_sync_context(code="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER")
        if not self.is_available():
            raise RuntimeError("E_SDK_MODEL_PROVIDER_CLOSED")
        messages: list[dict[str, str]] = []
        if str(request.system_prompt or "").strip():
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_message})
        response = run_coro_sync(
            self._provider.complete(
                messages=messages,
                runtime_context={
                    "local_prompt_max_output_tokens": request.max_tokens,
                    "local_prompt_temperature": request.temperature,
                    "local_prompt_stop_sequences": list(request.stop_sequences),
                },
            ),
            owner=self._coroutines,
        )
        raw = dict(response.raw or {})
        return GenerateResponse(
            text=str(response.content or ""),
            model=str(raw.get("model") or self._provider.model),
            latency_ms=nonnegative_int_or_none(raw.get("latency_ms")),
            input_tokens=nonnegative_int_or_none(raw.get("input_tokens")),
            output_tokens=nonnegative_int_or_none(raw.get("output_tokens")),
        )

    def is_available(self) -> bool:
        return not self._closed and self._coroutines.accepting

    def close(self) -> None:
        """Drain generation, close HTTP resources on their loop, then close that loop."""
        require_sync_context(code="E_SYNC_COROUTINE_REQUIRES_ASYNC_OWNER")
        try:
            self._coroutines.close(self._provider.close)
        finally:
            self._closed = self._coroutines.closed
