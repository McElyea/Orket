"""Deprecated compatibility package for modules moved to `orket.core.domain`."""

from __future__ import annotations

import sys
import types
import warnings
from typing import Any

from orket.core.domain import (
    bug_fix_phase,
    critical_path,
    failure_reporter,
    fixture_verifier,
    reconciler,
    sandbox,
    sandbox_verifier,
    verification,
    verification_runner,
)
from orket.core.domain.bug_fix_phase import (
    BugDiscoveryMetrics,
    BugFixPhase,
    BugFixPhaseStatus,
)
from orket.core.domain.critical_path import CriticalPathEngine
from orket.core.domain.execution import ExecutionResult, ExecutionTurn, ToolCall, ToolCallErrorClass
from orket.core.domain.failure_reporter import FailureReporter, PolicyViolationReport
from orket.core.domain.fixture_verifier import FixtureVerifier, VerificationSecurityError
from orket.core.domain.reconciler import StructuralReconciler
from orket.core.domain.records import CardRecord, IssueRecord
from orket.core.domain.sandbox import PortAllocation, Sandbox, SandboxRegistry, SandboxStatus, TechStack
from orket.core.domain.sandbox_verifier import SandboxVerifier
from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.core.domain.verification import AGENT_OUTPUT_DIR, VERIFICATION_DIR, VerificationEngine
from orket.core.domain.verification_runner import RUNNER_CODE
from orket.schema import WaitReason

warnings.warn("`orket.domain` is deprecated; import from `orket.core.domain` instead.", DeprecationWarning, stacklevel=2)

_MODULE_ALIASES = {
    "bug_fix_phase": bug_fix_phase,
    "critical_path": critical_path,
    "failure_reporter": failure_reporter,
    "fixture_verifier": fixture_verifier,
    "reconciler": reconciler,
    "sandbox": sandbox,
    "sandbox_verifier": sandbox_verifier,
    "verification": verification,
    "verification_runner": verification_runner,
}


def _register_alias(module_name: str, module: types.ModuleType) -> None:
    sys.modules.setdefault(f"{__name__}.{module_name}", module)
    setattr(sys.modules[__name__], module_name, module)


for _legacy_name, _target in _MODULE_ALIASES.items():
    _register_alias(_legacy_name, _target)

_records_module: Any = types.ModuleType(f"{__name__}.records")
_records_module.CardRecord = CardRecord
_records_module.IssueRecord = IssueRecord
_records_module.__all__ = ["IssueRecord", "CardRecord"]
sys.modules.setdefault(f"{__name__}.records", _records_module)
records = _records_module

_state_machine_module: Any = types.ModuleType(f"{__name__}.state_machine")
_state_machine_module.StateMachine = StateMachine
_state_machine_module.StateMachineError = StateMachineError
_state_machine_module.WaitReason = WaitReason
_state_machine_module.__all__ = ["StateMachine", "StateMachineError", "WaitReason"]
sys.modules.setdefault(f"{__name__}.state_machine", _state_machine_module)
state_machine = _state_machine_module

__all__ = [
    "AGENT_OUTPUT_DIR",
    "BugDiscoveryMetrics",
    "BugFixPhase",
    "BugFixPhaseStatus",
    "CardRecord",
    "CriticalPathEngine",
    "ExecutionResult",
    "ExecutionTurn",
    "FailureReporter",
    "FixtureVerifier",
    "IssueRecord",
    "PolicyViolationReport",
    "PortAllocation",
    "RUNNER_CODE",
    "Sandbox",
    "SandboxRegistry",
    "SandboxStatus",
    "SandboxVerifier",
    "StateMachine",
    "StateMachineError",
    "StructuralReconciler",
    "TechStack",
    "ToolCall",
    "ToolCallErrorClass",
    "VERIFICATION_DIR",
    "VerificationEngine",
    "VerificationSecurityError",
    "WaitReason",
]
