"""Deprecated compatibility module for `orket.core.domain.execution`."""

from __future__ import annotations

import warnings

from orket.core.domain.execution import ExecutionResult, ExecutionTurn, ToolCall

warnings.warn(
    "`orket.domain.execution` is deprecated; import from `orket.core.domain.execution` instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ExecutionResult", "ExecutionTurn", "ToolCall"]
