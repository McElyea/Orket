"""Compatibility shim: tool gate moved to `orket.core.policies.tool_gate`."""

from orket.core.policies.tool_gate import ToolGate, ToolGateViolation

__all__ = ["ToolGate", "ToolGateViolation"]
