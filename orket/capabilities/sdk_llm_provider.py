from __future__ import annotations

from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.capabilities.sync_bridge import run_coro_sync
from orket_extension_sdk.llm import GenerateRequest, GenerateResponse


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class LocalModelCapabilityProvider:
    """SDK `model.generate` provider backed by Orket LocalModelProvider."""

    def __init__(
        self,
        *,
        model: str,
        temperature: float,
        seed: int | None,
        timeout: int = 300,
    ) -> None:
        self._provider = LocalModelProvider(
            model=model,
            temperature=temperature,
            seed=seed,
            timeout=timeout,
        )

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        messages: list[dict[str, str]] = []
        if str(request.system_prompt or "").strip():
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.user_message})
        response = run_coro_sync(
            self._provider.complete(
                messages=messages,
                runtime_context={},
            )
        )
        raw = dict(response.raw or {})
        return GenerateResponse(
            text=str(response.content or ""),
            model=str(raw.get("model") or self._provider.model),
            latency_ms=int(_coerce_int(raw.get("latency_ms")) or 0),
            input_tokens=_coerce_int(raw.get("input_tokens")),
            output_tokens=_coerce_int(raw.get("output_tokens")),
        )

    def is_available(self) -> bool:
        return True
