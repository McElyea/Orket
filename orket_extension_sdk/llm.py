from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


def nonnegative_int_or_none(value: object) -> int | None:
    """Retain integer observations without coercing malformed metadata."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


@dataclass(frozen=True)
class GenerateRequest:
    """Input to LLM generation.

    Set max_tokens to the maximum safe output length for your model. 128
    causes truncation for most tasks.
    """

    system_prompt: str
    user_message: str
    max_tokens: int = 2048
    temperature: float = 0.7
    stop_sequences: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.max_tokens < 256:
            warnings.warn(
                "GenerateRequest.max_tokens below 256 can truncate governed outputs.",
                RuntimeWarning,
                stacklevel=2,
            )


@dataclass(frozen=True)
class GenerateResponse:
    """Output from LLM generation."""

    text: str
    model: str
    latency_ms: int | None
    input_tokens: int | None = None
    output_tokens: int | None = None
    schema_version: Literal["model_generate_response.v1"] = field(default="model_generate_response.v1", init=False)
    latency_posture: Literal["reported", "unavailable"] = field(init=False)

    def __post_init__(self) -> None:
        if self.latency_ms is not None and nonnegative_int_or_none(self.latency_ms) is None:
            raise ValueError("E_SDK_GENERATE_LATENCY_INVALID")
        object.__setattr__(self, "latency_posture", "reported" if self.latency_ms is not None else "unavailable")


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
        return GenerateResponse(text="", model="null", latency_ms=None)

    def is_available(self) -> bool:
        return False
