from __future__ import annotations

from orket_extension_sdk.llm import GenerateRequest, GenerateResponse


class StaticLLMCapabilityProvider:
    """Deterministic SDK provider used for bounded host-configured capability tests."""

    def __init__(self, *, text: str, model: str = "static-test-model") -> None:
        self._text = str(text)
        self._model = str(model)

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        del request
        return GenerateResponse(text=self._text, model=self._model, latency_ms=0, input_tokens=0, output_tokens=0)

    def is_available(self) -> bool:
        return True
