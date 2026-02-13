"""Compatibility shim: state machine moved to `orket.core.domain.state_machine`."""

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import WaitReason

__all__ = ["StateMachine", "StateMachineError", "WaitReason"]
