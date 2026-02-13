"""Compatibility shim: LLM provider moved to `orket.adapters.llm.local_model_provider`."""

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse

__all__ = ["LocalModelProvider", "ModelResponse"]
