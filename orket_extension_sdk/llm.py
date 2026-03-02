from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GenerateRequest:
    """Input to LLM generation."""

    system_prompt: str
    user_message: str
    max_tokens: int = 128
    temperature: float = 0.7
    stop_sequences: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GenerateResponse:
    """Output from LLM generation."""

    text: str
    model: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, request: GenerateRequest) -> GenerateResponse:
        ...

    def is_available(self) -> bool:
        ...


class NullLLMProvider:
    """Deterministic fallback when no LLM backend is available."""

    def generate(self, request: GenerateRequest) -> GenerateResponse:
        del request
        return GenerateResponse(text="", model="null", latency_ms=0)

    def is_available(self) -> bool:
        return False
