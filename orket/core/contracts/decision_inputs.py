"""Immutable values supplied to strategy and provider construction boundaries."""

from __future__ import annotations

from dataclasses import dataclass

ScalarLimit = str | int | float | bool | None


@dataclass(frozen=True)
class LoopPolicyInputs:
    concurrency: ScalarLimit = None
    max_iterations: ScalarLimit = None
    configured_max_iterations: ScalarLimit = None
    context_window: ScalarLimit = None


@dataclass(frozen=True)
class ModelClientOptions:
    temperature: float
    timeout: float


@dataclass(frozen=True)
class ToolSelectionInput:
    available_names: tuple[str, ...]
